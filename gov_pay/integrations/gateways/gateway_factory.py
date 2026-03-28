"""Factory for creating payment gateway instances."""

from gov_pay.config.settings import AppSettings
from gov_pay.domain.enums.payment_enums import GatewayProvider
from gov_pay.integrations.gateways.authorize_net_gateway import AuthorizeNetGateway
from gov_pay.integrations.gateways.base import PaymentGateway
from gov_pay.integrations.gateways.stripe_gateway import StripeGateway


class GatewayFactory:
    """Creates payment gateway instances based on provider configuration."""

    @staticmethod
    def create(provider: str, settings: AppSettings) -> PaymentGateway:
        if provider == GatewayProvider.STRIPE:
            return StripeGateway(
                secret_key=settings.gateway.stripe_secret_key,
                webhook_secret=settings.gateway.stripe_webhook_secret,
            )
        elif provider == GatewayProvider.AUTHORIZE_NET:
            return AuthorizeNetGateway(
                api_login_id=settings.gateway.authnet_api_login_id,
                transaction_key=settings.gateway.authnet_transaction_key,
                sandbox=settings.gateway.authnet_sandbox,
            )
        else:
            raise ValueError(f"Unsupported gateway provider: {provider}")
