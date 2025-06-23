import pytest
from unittest.mock import AsyncMock, patch
from forth_ai_underwriting.services.validation import ValidationService
from forth_ai_underwriting.core.schemas import ValidationResult

@pytest.fixture
def validation_service():
    with patch('forth_ai_underwriting.services.validation.httpx.AsyncClient') as MockAsyncClient:
        mock_client = MockAsyncClient.return_value
        mock_client.get.return_value = AsyncMock(status_code=200, json=lambda: {})
        service = ValidationService()
        service.forth_client = mock_client
        return service

@pytest.mark.asyncio
async def test_validate_hardship_pass(validation_service):
    contact_data = {"custom_fields": {"hardship_description": "Lost my job due to company downsizing."}}
    results = await validation_service._validate_hardship(contact_data)
    assert len(results) == 1
    assert results[0].result == "Pass"
    assert "Valid financial hardship description" in results[0].reason

@pytest.mark.asyncio
async def test_validate_hardship_no_pass_empty(validation_service):
    contact_data = {"custom_fields": {"hardship_description": ""}}
    results = await validation_service._validate_hardship(contact_data)
    assert len(results) == 1
    assert results[0].result == "No Pass"
    assert "No hardship description provided" in results[0].reason

@pytest.mark.asyncio
async def test_validate_budget_analysis_pass(validation_service):
    contact_data = {"budget_analysis": {"income": 5000, "expenses": 4000}}
    results = await validation_service._validate_budget_analysis(contact_data)
    assert len(results) == 1
    assert results[0].result == "Pass"
    assert "Positive surplus of $1000.00" in results[0].reason

@pytest.mark.asyncio
async def test_validate_budget_analysis_no_pass_negative(validation_service):
    contact_data = {"budget_analysis": {"income": 3000, "expenses": 4000}}
    results = await validation_service._validate_budget_analysis(contact_data)
    assert len(results) == 1
    assert results[0].result == "No Pass"
    assert "Negative surplus of $-1000.00" in results[0].reason

@pytest.mark.asyncio
async def test_validate_address_pass(validation_service):
    contact_data = {"address": {"state": "CA"}, "assigned_company": "Faye Caulin"}
    results = await validation_service._validate_address(contact_data)
    assert len(results) == 1
    assert results[0].result == "Pass"
    assert "correctly assigned to 'Faye Caulin'" in results[0].reason

@pytest.mark.asyncio
async def test_validate_address_no_pass_mismatch(validation_service):
    contact_data = {"address": {"state": "AL"}, "assigned_company": "Faye Caulin"}
    results = await validation_service._validate_address(contact_data)
    assert len(results) == 1
    assert results[0].result == "No Pass"
    assert "should be assigned to 'Concordia Legal Advisors', but assigned to 'Faye Caulin'" in results[0].reason

@pytest.mark.asyncio
async def test_validate_draft_min_payment_pass(validation_service):
    contact_data = {"contract": {"monthly_payment": 300}}
    results = await validation_service._validate_draft(contact_data)
    assert len(results) >= 1  # May have other draft checks
    assert any(r.title == "Draft - Minimum Payment" and r.result == "Pass" for r in results)

@pytest.mark.asyncio
async def test_validate_draft_min_payment_no_pass(validation_service):
    contact_data = {"contract": {"monthly_payment": 200}}
    results = await validation_service._validate_draft(contact_data)
    assert len(results) >= 1
    assert any(r.title == "Draft - Minimum Payment" and r.result == "No Pass" for r in results)

@pytest.mark.asyncio
async def test_validate_draft_timing_pass(validation_service):
    contact_data = {"enrollment_date": "2025-01-01", "first_draft_date": "2025-01-15", "affiliate": ""}
    results = await validation_service._validate_draft(contact_data)
    assert len(results) >= 1
    assert any(r.title == "Draft - Timing" and r.result == "Pass" for r in results)

@pytest.mark.asyncio
async def test_validate_draft_timing_credit_care_exception(validation_service):
    contact_data = {"enrollment_date": "2025-01-01", "first_draft_date": "2025-02-10", "affiliate": "Credit Care"}
    results = await validation_service._validate_draft(contact_data)
    assert len(results) >= 1
    assert any(r.title == "Draft - Timing" and r.result == "Pass" for r in results)

@pytest.mark.asyncio
async def test_validate_contract_ip_pass(validation_service):
    parsed_data = {"sender_ip": "1.1.1.1", "signer_ip": "2.2.2.2"}
    results = await validation_service._validate_contract({}, parsed_data)
    assert any(r.title == "Contract - IP Addresses" and r.result == "Pass" for r in results)

@pytest.mark.asyncio
async def test_validate_contract_ip_no_pass(validation_service):
    parsed_data = {"sender_ip": "1.1.1.1", "signer_ip": "1.1.1.1"}
    results = await validation_service._validate_contract({}, parsed_data)
    assert any(r.title == "Contract - IP Addresses" and r.result == "No Pass" for r in results)

@pytest.mark.asyncio
async def test_validate_contract_mailing_address_pass(validation_service):
    contact_data = {"address": {"street": "123 Main St", "city": "Anytown", "state": "CA", "zip_code": "90210"}}
    parsed_data = {"mailing_address": {"street": "123 Main St", "city": "Anytown", "state": "CA", "zip_code": "90210"}}
    results = await validation_service._validate_contract(contact_data, parsed_data)
    assert any(r.title == "Contract - Mailing Address" and r.result == "Pass" for r in results)

@pytest.mark.asyncio
async def test_validate_contract_signatures_pass(validation_service):
    parsed_data = {"signatures": {"applicant": "JohnDoe", "co_applicant": "JaneDoe"}}
    results = await validation_service._validate_contract({}, parsed_data)
    assert any(r.title == "Contract - Signatures" and r.result == "Pass" for r in results)

@pytest.mark.asyncio
async def test_validate_contract_signatures_no_pass_dots(validation_service):
    parsed_data = {"signatures": {"applicant": "John.Doe", "co_applicant": "JaneDoe"}}
    results = await validation_service._validate_contract({}, parsed_data)
    assert any(r.title == "Contract - Signatures" and r.result == "No Pass" for r in results)

@pytest.mark.asyncio
async def test_validate_contract_bank_details_pass(validation_service):
    contact_data = {"bank_details": {"account_number": "123", "routing_number": "456"}}
    parsed_data = {"bank_details": {"account_number": "123", "routing_number": "456"}}
    results = await validation_service._validate_contract(contact_data, parsed_data)
    assert any(r.title == "Contract - Bank Details" and r.result == "Pass" for r in results)

@pytest.mark.asyncio
async def test_validate_contract_ssn_pass(validation_service):
    contact_data = {"credit_report": {"ssn": "123-45-6789"}}
    parsed_data = {"gateway": {"ssn_last4": "6789"}, "agreement": {"ssn": "123-45-6789"}}
    results = await validation_service._validate_contract(contact_data, parsed_data)
    assert any(r.title == "Contract - SSN Consistency" and r.result == "Pass" for r in results)

@pytest.mark.asyncio
async def test_validate_contract_dob_pass(validation_service):
    contact_data = {"date_of_birth": "1990-01-01", "credit_report": {"date_of_birth": "1990-01-01"}}
    parsed_data = {"agreement": {"date_of_birth": "1990-01-01"}}
    results = await validation_service._validate_contract(contact_data, parsed_data)
    assert any(r.title == "Contract - DOB Consistency" and r.result == "Pass" for r in results)


