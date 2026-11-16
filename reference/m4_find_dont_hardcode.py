"""Milestone 4, reference (fast path): a registry in dicts with word-overlap discovery, and a tracer in dicts."""

from __future__ import annotations

import re
from typing import Any

from groundstop.company import load_company
from groundstop.mesh import Env, Mesh, Message
from groundstop.mesh.naive import DirectTransport, NoClaims, NoIdentity, OpenGate

STOP = {
    "a",
    "an",
    "the",
    "to",
    "of",
    "for",
    "in",
    "on",
    "at",
    "and",
    "or",
    "with",
    "their",
    "its",
    "each",
    "this",
    "that",
    "is",
    "may",
    "it",
}
MATCH = 0.5  # share of the request's words that must be in the purpose


def words(text: str) -> set[str]:
    out = set()
    for w in re.findall(r"[a-z]+", text.lower()):
        if w in STOP:
            continue
        out.add(w[:-1] if len(w) > 3 and w.endswith("s") else w)
    return out


class Registry:
    def bind(self, env: Env, mesh: Mesh) -> None:
        self.env, self.mesh = env, mesh
        company = load_company()
        self.topics = {s.id: dict(s.publishes) for s in company.agents.values()}
        self.people = company.people
        self.internal = {s.id for s in company.agents.values() if not s.outside} | set(company.gateways)
        self.records: list[dict[str, Any]] = []
        self.log: list[dict[str, Any]] = []

    def subscribers(self, caller: str, topic: str) -> list[str]:
        return list(self.topics.get(caller, {}).get(topic, []))

    def _role(self, person: str) -> tuple[str | None, str | None]:
        info = self.people.get(person)
        return (info["team"], info["role"]) if info else (None, None)

    def _note(self, action: str, agent: str, version: str | None, by: str, ok: bool) -> bool:
        team, role = self._role(by)
        self.log.append(
            {"at": self.env.now, "action": action, "agent": agent, "version": version, "by": by, "role": role, "ok": ok}
        )
        return ok

    def _may_publish(self, entry: dict, person: str) -> bool:
        team, role = self._role(person)
        if role == "developer":
            return team == entry.get("owner")
        if role == "partner":
            return team == f"partner:{entry['id']}" and entry.get("owner") == team
        return False

    def publish(self, entry: dict[str, Any], by: str) -> bool:
        ok = self._may_publish(entry, by)
        if ok:
            self.records.append(dict(entry, status="pending", published_by=by))
        return self._note("publish", entry.get("id", "?"), entry.get("version"), by, ok)

    def approve(self, agent: str, version: str, by: str) -> bool:
        _, role = self._role(by)
        pending = next(
            (r for r in self.records if r["id"] == agent and r["version"] == version and r["status"] == "pending"), None
        )
        ok = role == "reviewer" and pending is not None
        if ok:
            for r in self.records:
                if r["id"] == agent and r["status"] == "active":
                    r["status"] = "superseded"
            pending["status"] = "active"
        return self._note("approve", agent, version, by, ok)

    def retire(self, agent: str, by: str) -> bool:
        team, role = self._role(by)
        active = self._active(agent)
        ok = active is not None and ((role == "developer" and team == active["owner"]) or role == "reviewer")
        if ok:
            active["status"] = "retired"
        return self._note("retire", agent, active["version"] if active else None, by, ok)

    def entries(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self.records]

    def audit(self) -> list[dict[str, Any]]:
        return list(self.log)

    def _active(self, agent: str) -> dict | None:
        return next((r for r in self.records if r["id"] == agent and r["status"] == "active"), None)

    def resolve(self, caller: str, name: str) -> str | None:
        if name.startswith(("http://", "https://")):
            return name
        entry = self._active(name)
        return entry["address"] if entry else None

    def find(self, caller: str, purpose: str) -> str | None:
        org = "fragata" if caller in self.internal else "partner"
        want = words(purpose)
        best, best_score = None, 0.0
        for r in self.records:
            if r["status"] != "active" or r["id"] == caller or org not in r.get("visibility", []):
                continue
            score = len(want & words(r["purpose"])) / len(want) if want else 0.0
            if score > best_score or (score == best_score and best and r["id"] < best):
                best, best_score = r["id"], score
        return best if best_score >= MATCH else None


class Tracer:
    def bind(self, env: Env, mesh: Mesh) -> None:
        self.env = env
        self.spans: dict[int, dict[str, Any]] = {}
        self.by_pax: dict[str, str] = {}
        self.order: dict[str, list[int]] = {}

    def stamp(self, msg: Message, parent: Message | None) -> None:
        pax = msg.body.get("pax")
        if isinstance(pax, str):
            msg.trace = self.by_pax.setdefault(pax, f"T-{pax}")
        elif parent is not None and parent.trace:
            msg.trace = parent.trace
        else:
            msg.trace = f"T-{msg.id}"
        self.spans[msg.id] = {
            "id": msg.id, "parent": msg.parent, "sender": msg.sender, "to": msg.to, "kind": msg.kind,
            "sent_at": msg.sent_at, "handled_at": None, "trace": msg.trace,
        }  # fmt: skip
        self.order.setdefault(msg.trace, []).append(msg.id)

    def handled(self, agent: str, msg: Message) -> None:
        if msg.id in self.spans and self.spans[msg.id]["handled_at"] is None:
            self.spans[msg.id]["handled_at"] = self.env.now

    def trace_of(self, pax: str) -> str | None:
        return self.by_pax.get(pax)

    def trace(self, trace_id: str) -> list[dict[str, Any]]:
        return [dict(self.spans[i]) for i in self.order.get(trace_id, [])]

    def slowest_hop(self, trace_id: str) -> dict[str, Any]:
        spans = self.trace(trace_id)
        first_child: dict[int, float] = {}
        for s in spans:
            if s["parent"] is not None and s["parent"] not in first_child:
                first_child[s["parent"]] = s["sent_at"]
        best = {"agent": None, "seconds": -1.0}
        for s in spans:
            end = first_child.get(s["id"], s["handled_at"])
            if end is None:
                continue
            if end - s["sent_at"] > best["seconds"]:
                best = {"agent": s["to"], "seconds": end - s["sent_at"]}
        return best


def build() -> Mesh:
    return Mesh("registry", Registry(), DirectTransport(), NoClaims(), NoIdentity(), OpenGate(), Tracer())
