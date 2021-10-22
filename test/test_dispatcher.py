import pytest
import asyncio
import sys, os
import struct
import binascii
sys.path.append(os.path.realpath(os.path.dirname(__file__)+"/.."))
import conftest
from pos_proxy.client import MessageHandlingType, SocketClientError
from pos_proxy.dispatcher import DispatchedMessage
from pos_proxy.passport_handler import PassportHandler

@pytest.mark.asyncio
async def test_get_valid_clients(mute_passport_dispatcher):
    dispatched_message = DispatchedMessage(conftest.FINALIZE_REWARDS_REQUEST)
    valid_clients = mute_passport_dispatcher.get_valid_clients(dispatched_message = dispatched_message, message_type = MessageHandlingType.CARD_BASED_UNICAST, routing_id = conftest.CARD_IN_FRR, session_id = conftest.SESSION_IN_FRR)
    assert valid_clients == mute_passport_dispatcher.clients[:1]

@pytest.mark.asyncio
async def test_dispatch_to_client(mute_passport_dispatcher, good_passport_client):
    await mute_passport_dispatcher.dispatch_to_client_and_respond_if_first_answer(DispatchedMessage(conftest.FINALIZE_REWARDS_REQUEST), good_passport_client)

@pytest.mark.asyncio
async def test_server_send(server_passport_reader_writer):
    reader = server_passport_reader_writer[0]
    writer = server_passport_reader_writer[1]
    writer.write(conftest.FINALIZE_REWARDS_REQUEST)    
    length, header = await PassportHandler().read_and_process_header(reader)
    assert length == len(conftest.FINALIZE_REWARDS_REQUEST) - len(header)    
    assert header == conftest.FINALIZE_REWARDS_REQUEST[0:28]
    
    
@pytest.mark.asyncio
async def test_multi_server_send(server_multi_passport_reader_writer):
    reader = server_multi_passport_reader_writer[0]
    writer = server_multi_passport_reader_writer[1]
    mock_host_1 = server_multi_passport_reader_writer[2]
    mock_host_2 = server_multi_passport_reader_writer[3]
    assert mock_host_1.message_received == False
    assert mock_host_2.message_received == False
    writer.write(conftest.GOOD_PASSPORT_ONL_STATUS)          
    length, header = await PassportHandler().read_and_process_header(reader)
    assert length == len(conftest.GOOD_PASSPORT_ONL_STATUS) - len(header)    
    assert header == conftest.GOOD_PASSPORT_ONL_STATUS[0:28]
    assert mock_host_1.message_received == True
    assert mock_host_2.message_received == True
    
@pytest.mark.asyncio
async def test_multi_server_send_one_times_out(server_multi_passport_reader_writer_one_times_out):
    reader = server_multi_passport_reader_writer_one_times_out[0]
    writer = server_multi_passport_reader_writer_one_times_out[1]
    mock_host_1 = server_multi_passport_reader_writer_one_times_out[2]
    mock_host_2 = server_multi_passport_reader_writer_one_times_out[3]
    assert mock_host_1.message_received == False
    assert mock_host_2.message_received == False
    writer.write(conftest.GOOD_PASSPORT_ONL_STATUS)       
    length, header = await PassportHandler().read_and_process_header(reader)
    assert length == len(conftest.GOOD_PASSPORT_ONL_STATUS) - len(header)    
    assert header == conftest.GOOD_PASSPORT_ONL_STATUS[0:28]
    assert mock_host_1.message_received == True
    assert mock_host_2.message_received == True


@pytest.mark.asyncio
async def test_multi_server_send_grr(server_multi_passport_reader_writer):
    reader = server_multi_passport_reader_writer[0]
    writer = server_multi_passport_reader_writer[1]
    mock_host_1 = server_multi_passport_reader_writer[2]
    mock_host_2 = server_multi_passport_reader_writer[3]
    assert mock_host_1.message_received == False
    assert mock_host_2.message_received == False
    writer.write(conftest.GET_REWARDS_REQUEST)       
    length, header = await PassportHandler().read_and_process_header(reader)
    assert length == len(conftest.GET_REWARDS_REQUEST) - len(header)    
    assert header == conftest.GET_REWARDS_REQUEST[0:28]
    assert mock_host_1.message_received == True
    assert mock_host_2.message_received == False


@pytest.mark.asyncio
async def test_multi_server_send_grr_2_invalid_crc(server_multi_passport_reader_writer):
    reader = server_multi_passport_reader_writer[0]
    writer = server_multi_passport_reader_writer[1]
    mock_host_1 = server_multi_passport_reader_writer[2]
    mock_host_2 = server_multi_passport_reader_writer[3]
    assert mock_host_1.message_received == False
    assert mock_host_2.message_received == False
    writer.write(conftest.GET_REWARDS_REQUEST_2_INVALID)       
    with pytest.raises(SocketClientError):
        await PassportHandler().read_and_process_header(reader)

@pytest.mark.asyncio
async def test_multi_server_send_grr_2_valid_crc(server_multi_passport_reader_writer):
    reader = server_multi_passport_reader_writer[0]
    writer = server_multi_passport_reader_writer[1]
    mock_host_1 = server_multi_passport_reader_writer[2]
    mock_host_2 = server_multi_passport_reader_writer[3]
    assert mock_host_1.message_received == False
    assert mock_host_2.message_received == False
    writer.write(conftest.GET_REWARDS_REQUEST_2_VALID)       
    
    await PassportHandler().read_and_process_header(reader)

    assert mock_host_1.message_received == False
    assert mock_host_2.message_received == True
    
@pytest.mark.asyncio
async def test_multi_server_send_multiple(server_multi_passport_reader_writer):
    reader = server_multi_passport_reader_writer[0]
    writer = server_multi_passport_reader_writer[1]
    mock_host_1 = server_multi_passport_reader_writer[2]
    mock_host_2 = server_multi_passport_reader_writer[3]
    assert mock_host_1.message_received == False
    assert mock_host_2.message_received == False
    writer.write(conftest.GOOD_PASSPORT_ONL_STATUS)       
    response, _, _ = await PassportHandler().wait_and_handle_response_message(reader,conftest.GOOD_PASSPORT_ONL_STATUS)
    assert response == conftest.GOOD_PASSPORT_ONL_STATUS
    assert mock_host_1.message_received == True
    assert mock_host_2.message_received == True
    mock_host_1.message_received = False
    mock_host_2.message_received = False

    writer.write(conftest.GET_REWARDS_REQUEST)       
    response, _, _  = await PassportHandler().wait_and_handle_response_message(reader,conftest.GET_REWARDS_REQUEST)
    assert response == conftest.GET_REWARDS_REQUEST
    assert mock_host_1.message_received == True
    assert mock_host_2.message_received == False
    mock_host_1.message_received = False
    mock_host_2.message_received = False

    writer.write(conftest.GET_REWARDS_REQUEST_2_VALID)       
    response, _, _ = await PassportHandler().wait_and_handle_response_message(reader,conftest.GET_REWARDS_REQUEST_2_VALID)
    assert response == conftest.GET_REWARDS_REQUEST_2_VALID
    assert mock_host_1.message_received == False
    assert mock_host_2.message_received == True
    mock_host_1.message_received = False
    mock_host_2.message_received = False

    mock_host_1.timeout = True
    mock_host_2.timeout = True
    mock_host_1.message_received_event.clear()
    mock_host_2.message_received_event.clear()
    writer.write(conftest.END_CUSTOMER_REQUEST)      
    response, _, _ = await PassportHandler().wait_and_handle_response_message(reader,conftest.END_CUSTOMER_REQUEST)
    assert response is None  
    await mock_host_1.message_received_event.wait() 
    await mock_host_2.message_received_event.wait() 
    assert mock_host_1.message_received == True
    assert mock_host_2.message_received == True
    mock_host_1.message_received = False
    mock_host_2.message_received = False    
    mock_host_1.timeout = False
    mock_host_2.timeout = False

    writer.write(conftest.GET_REWARDS_REQUEST_2_VALID)       
    response, _, _ = await PassportHandler().wait_and_handle_response_message(reader,conftest.GET_REWARDS_REQUEST_2_VALID)
    assert response == conftest.GET_REWARDS_REQUEST_2_VALID
    assert mock_host_1.message_received == False
    assert mock_host_2.message_received == True
    mock_host_1.message_received = False
    mock_host_2.message_received = False

@pytest.mark.asyncio
async def test_multi_server_send_multiple_fast(server_multi_passport_reader_writer):
    reader = server_multi_passport_reader_writer[0]
    writer = server_multi_passport_reader_writer[1]    
    
    writer.write(conftest.GOOD_PASSPORT_ONL_STATUS) 

    await PassportHandler().wait_and_handle_response_message(reader,conftest.GOOD_PASSPORT_ONL_STATUS) 

    writer.write(conftest.GET_REWARDS_REQUEST)   
    writer.write(conftest.GET_REWARDS_REQUEST_2_VALID)  

    await PassportHandler().wait_and_handle_response_message(reader,conftest.GET_REWARDS_REQUEST)
    await PassportHandler().wait_and_handle_response_message(reader,conftest.GET_REWARDS_REQUEST_2_VALID)

    writer.write(conftest.GET_REWARDS_REQUEST)  
    await PassportHandler().wait_and_handle_response_message(reader,conftest.GET_REWARDS_REQUEST)

    writer.write(conftest.FINALIZE_REWARDS_REQUEST)  
    await PassportHandler().wait_and_handle_response_message(reader,conftest.FINALIZE_REWARDS_REQUEST)

    writer.write(conftest.GOOD_PASSPORT_ONL_STATUS)   
    await PassportHandler().wait_and_handle_response_message(reader,conftest.GOOD_PASSPORT_ONL_STATUS)
    
    #response order is not guaranteed (by design)
    
    