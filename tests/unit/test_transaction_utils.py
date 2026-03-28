"""Unit tests for transaction utilities."""

from gov_pay.utils.transaction_utils import (
    generate_batch_id,
    generate_refund_number,
    generate_transaction_number,
    mask_account_number,
    mask_card_number,
)


class TestTransactionNumberGeneration:
    def test_transaction_number_format(self):
        number = generate_transaction_number("GOV")
        parts = number.split("-")
        assert len(parts) == 3
        assert parts[0] == "GOV"
        assert len(parts[1]) == 8  # YYYYMMDD
        assert len(parts[2]) == 8  # Short UUID

    def test_transaction_number_custom_prefix(self):
        number = generate_transaction_number("STATE")
        assert number.startswith("STATE-")

    def test_refund_number_format(self):
        number = generate_refund_number("REF")
        assert number.startswith("REF-")

    def test_uniqueness(self):
        numbers = {generate_transaction_number("GOV") for _ in range(100)}
        assert len(numbers) == 100


class TestMasking:
    def test_mask_card_number(self):
        assert mask_card_number("4111111111111234") == "1234"

    def test_mask_card_short(self):
        assert mask_card_number("12") == "12"

    def test_mask_account_number(self):
        assert mask_account_number("123456789") == "6789"

    def test_batch_id_format(self):
        bid = generate_batch_id("abc12345-def")
        assert bid.startswith("BATCH-abc12345")
