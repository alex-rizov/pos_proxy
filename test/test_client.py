import pytest
import asyncio
import sys, os
sys.path.append(os.path.realpath(os.path.dirname(__file__)+"/.."))
import conftest

#Tests
@pytest.mark.asyncio
async def test_connect(good_passport_client): 
    await good_passport_client.connect()
     

@pytest.mark.asyncio
async def test_send(good_passport_client):            
    await good_passport_client.send(conftest.GOOD_PASSPORT_ONL_STATUS)           
    
@pytest.mark.asyncio
async def test_bad_send(bad_passport_client):     
    with pytest.raises(ConnectionRefusedError):
        await bad_passport_client.send(conftest.GOOD_PASSPORT_ONL_STATUS)   

@pytest.mark.asyncio
async def test_wait_response(good_passport_client):            
     await good_passport_client.send_and_wait_response(conftest.GOOD_PASSPORT_ONL_STATUS)

@pytest.mark.asyncio
async def test_wait_response_good_wait(good_passport_client):            
     await good_passport_client.send_and_wait_response_with_timeout(conftest.GOOD_PASSPORT_ONL_STATUS)     

@pytest.mark.asyncio
async def test_wait_response_good_wait_finalize(good_passport_client):            
     await good_passport_client.send_and_wait_response_with_timeout(conftest.FINALIZE_REWARDS_REQUEST)        
    
@pytest.mark.asyncio
async def test_wait_response_bad_wait(impatient_passport_client):       
    with pytest.raises(asyncio.TimeoutError): 
        await impatient_passport_client.send_and_wait_response_with_timeout(conftest.GOOD_PASSPORT_ONL_STATUS)