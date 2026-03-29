"""Factory for creating payment gateway instances.

Supports two models:
1. Platform-managed gateways (Stripe, Authorize.Net) — credentials from app settings
2. BYOM (Bring Your Own Merchant) — credentials from entity config (Worldpay, HPP)

In the BYOM model, each county provides their own merchant account credentials.
Funds settle directly to the county's bank account. The platform never touches money.
"""

import json
from typing import Optional

from gov_pay.config.settings import AppSettings
from gov_pay.domain.enums.payment_enums import GatewayProvider
from gov_pay.integrations.gateways.authorize_net_gateway import AuthorizeNetGateway
from gov_pay.integrations.gateways.base import PaymentGateway
from gov_pay.integrations.gateways.hosted_payment_gateway import HostedPaymentPageGateway
from gov_pay.integrations.gateways.stripe_gateway import StripeGateway
from gov_pay.integrations.gateways.worldpay_gateway import WorldpayGateway


class GatewayFactory:
    """Creates payment gateway instances based on provider configuration.

    For platform-managed gateways (Stripe, Authorize.Net), uses app-level settings.
    For BYOM gateways (Worldpay, HPP), uses per-entity configuration.
    """

    @staticmethod
    def create(
        provider: str,
        settings: AppSettings,
        entity_gateway_config: Optional[str] = None,
    ) -> PaymentGateway:
        """Create a gateway instance.

        Args:
            provider: Gateway provider identifier
            settings: Application settings (for platform-managed gateways)
            entity_gateway_config: JSON string with entity-specific gateway
                                   credentials (for BYOM gateways)
        """
        # BYOM gateways — credentials come from entity config
        if provider == GatewayProvider.WORLDPAY:
            config = json.loads(entity_gateway_config) if entity_gateway_config else {}
            return WorldpayGateway(
                merchant_id=config.get("merchant_id", ""),
                terminal_id=config.get("terminal_id", ""),
                api_key=config.get("api_key", ""),
                sandbox=config.get("sandbox", True),
            )

        if provider == GatewayProvider.HOSTED_PAYMENT_PAGE:
            config = json.loads(entity_gateway_config) if entity_gateway_config else {}
            return HostedPaymentPageGateway(
                api_url=config.get("api_url", ""),
                merchant_id=config.get("merchant_id", ""),
                api_key=config.get("api_key", ""),
                api_secret=config.get("api_secret", ""),
                callback_url=config.get("callback_url", ""),
                sandbox=config.get("sandbox", True),
            )

        # Platform-managed gateways — credentials from app settings
        if provider == GatewayProvider.STRIPE:
            return StripeGateway(
                secret_key=settings.gateway.stripe_secret_key,
                webhook_secret=settings.gateway.stripe_webhook_secret,
            )

        if provider == GatewayProvider.AUTHORIZE_NET:
            return AuthorizeNetGateway(
                api_login_id=settings.gateway.authnet_api_login_id,
                transaction_key=settings.gateway.authnet_transaction_key,
                sandbox=settings.gateway.authnet_sandbox,
            )

        raise ValueError(f"Unsupported gateway provider: {provider}")
