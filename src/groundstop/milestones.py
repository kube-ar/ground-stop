"""The project's milestones: where your code goes, where its checks live, where to read about it."""

from __future__ import annotations

from dataclasses import dataclass

SITE = "https://kube.ar"
PROJECT = "ground-stop"
COURSE = "agentic-mesh"


@dataclass(frozen=True)
class Milestone:
    id: str
    slug: str
    title: dict[str, str]
    module: str  # your code
    reference: str  # the reference solution, relative to the repo root
    checks: str  # the module with `run(module)`

    @property
    def file(self) -> str:
        return "src/" + self.module.replace(".", "/") + ".py"

    def url(self, lang: str) -> str:
        prefix = "" if lang == "en" else f"/{lang}"
        return f"{SITE}{prefix}/{COURSE}/project/{PROJECT}/{self.slug}"


@dataclass(frozen=True)
class Lesson:
    """A section of a lesson on the site: slug, then (section title, anchor) per language."""

    slug: str
    sections: dict[str, tuple[str, str]]

    def title(self, lang: str) -> str:
        return self.sections[lang][0]

    def url(self, lang: str) -> str:
        prefix = "" if lang == "en" else f"/{lang}"
        return f"{SITE}{prefix}/{COURSE}/{self.slug}#{self.sections[lang][1]}"


def _m(n: int, slug: str, es: str, en: str) -> Milestone:
    name = f"m{n}_{slug.replace('-', '_')}"
    return Milestone(
        str(n), slug, {"es": es, "en": en}, f"groundstop.mine.{name}", f"reference/{name}.py", f"groundstop.checks.m{n}"
    )


MILESTONES = {
    m.id: m
    for m in [
        _m(0, "the-storm", "La tormenta", "The storm"),
        _m(1, "count-the-agents", "Contar los agentes", "Count the agents"),
    ]
}
