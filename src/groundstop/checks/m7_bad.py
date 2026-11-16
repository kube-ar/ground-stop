"""A bad version for milestone 7's pipeline: a decision that, on one passenger, also issues a voucher.

Its tests pass and its nights look fine. Only a scan of its code finds the call it never declared.
"""

from __future__ import annotations


def nosy_decide(good_cls):
    good = good_cls.decide

    def nosy(body, ctx):
        if body.get("pax") == "PX-00000":
            ctx.call("vouchers", "issue", pax=body["pax"], kind="meal", amount=15)
        return good(body, ctx)

    return nosy
