import pytest
import sys, os
import asyncio
sys.path.append(os.path.realpath(os.path.dirname(__file__)+"/.."))
import conftest
from pos_proxy.passport_handler import PassportHandler
from pos_proxy.client import MessageHandlingType

def test_process_end_customer_request():
    PassportHandler().process_header(conftest.END_CUSTOMER_REQUEST)

def test_process_echo():
    PassportHandler().process_header(conftest.GOOD_PASSPORT_ONL_STATUS)

def test_message_handling_type_onl_status():
    handling_type, id_string, session_id = PassportHandler().get_message_handling_type_and_identifier(conftest.GOOD_PASSPORT_ONL_STATUS)
    assert handling_type ==  MessageHandlingType.MULTICAST_WITH_RESPONSE
    assert id_string is None
    assert session_id is None

def test_message_handling_type_end_cust():
    handling_type, id_string, session_id = PassportHandler().get_message_handling_type_and_identifier(conftest.END_CUSTOMER_REQUEST)
    assert handling_type ==  MessageHandlingType.MULTICAST_NO_RESPONSE
    assert id_string is None
    assert session_id is None

def test_message_handling_type_get_rewards():
    handling_type, id_string, session_id = PassportHandler().get_message_handling_type_and_identifier(conftest.GET_REWARDS_REQUEST)
    assert handling_type ==  MessageHandlingType.CARD_BASED_UNICAST
    assert id_string == conftest.CARD_IN_GRR
    assert session_id is None

def test_message_handling_type_finalize_rewards():
    handling_type, id_string, session_id = PassportHandler().get_message_handling_type_and_identifier(conftest.FINALIZE_REWARDS_REQUEST)
    assert handling_type ==  MessageHandlingType.CARD_BASED_UNICAST
    assert id_string == conftest.CARD_IN_FRR
    assert session_id == conftest.SESSION_IN_FRR

@pytest.mark.asyncio
async def test_read_process_echo_header(echo_reader_writer):
    reader = echo_reader_writer[0]
    writer = echo_reader_writer[1]
    writer.write(conftest.GOOD_PASSPORT_ONL_STATUS)    
    length, header = await PassportHandler().read_and_process_header(reader)
    assert length == 420    
    assert header == conftest.GOOD_PASSPORT_ONL_STATUS[0:28]

@pytest.mark.asyncio
async def test_read_process_echo_message(echo_reader_writer):
    reader = echo_reader_writer[0]
    writer = echo_reader_writer[1]
    writer.write(conftest.GOOD_PASSPORT_ONL_STATUS)    
    await PassportHandler().wait_and_handle_response_message(reader, conftest.GOOD_PASSPORT_ONL_STATUS)   
    