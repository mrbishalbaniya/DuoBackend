from duo_project.throttling import FailOpenUserRateThrottle


class GiftCardRedeemThrottle(FailOpenUserRateThrottle):
    scope = "gift_redeem"
