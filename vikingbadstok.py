import requests
import json
import logging
import re
import os
from dotenv import load_dotenv

# load_dotenv('/home/abkh/nasaFiler/bad/.env.ProdBP')
load_dotenv('/home/allieradm/bad/.env.ProdBP')


def error_log(msg:str) -> None:
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.ERROR)

    file_handler = logging.FileHandler('errorlog.txt')
    log_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    file_handler.setFormatter(log_formatter)
    logger.addHandler(file_handler)
    logger.error(msg)


def debug_log(msg:str) -> None:
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    file_handler = logging.FileHandler('debuglog.txt')
    log_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    file_handler.setFormatter(log_formatter)
    logger.addHandler(file_handler)
    logger.debug(msg)



class VikingBadStock:
    def __init__(self):
        self.base_url = "https://api.vikingbad.no"
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        self.timeout = 10
        
    def get_stock(self) -> list[dict]|None:
        url = f"{self.base_url}/v0/stock"
        try:
            response = requests.get(url=url, headers=self.headers, timeout=self.timeout)
        except TimeoutError as e:
            error_log(f"Timeout error in get stock in vinkingbad stock class : {repr(e)}")
            return None
        except Exception as e:
            error_log(f"Failed getting a response in get stock in vinkingbad stock class, error : {repr(e)}")
            return None
            
        if response.status_code == 200:
            res:dict[list] = response.json()
            return res.get("data")
        else:
            error_log(f"getting error response in get stock in vikingbad. response code: {response.status_code}, response text: {response.text}")
            return None
        

class BrightpearlStock:
    def __init__(self):
        self.base_url = "https://euw1.brightpearlconnect.com/public-api/badnoas"
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "brightpearl-app-ref": os.getenv("PRICE_BP_APP_REFF"),
            "brightpearl-staff-token": os.getenv("PRICE_BP_STAFF_TOKEN")
        }

        self.timeout = 10

    def get_product_availability(self, productID:str, warehouseID: str) -> int|None|str:
        '''returns int if there is in stock, None if error, str if inStock not provided in the api data'''
        url = f"{self.base_url}/warehouse-service/product-availability/{productID}"
        try:
            response = requests.get(url=url, headers=self.headers, timeout=self.timeout)
        except TimeoutError as e:
            error_log(f"Timeout error in get availability: {repr(e)}")
            return None
        except Exception as e:
            error_log(f"Failed getting a response in get availability, error : {repr(e)}")
            return None
            
        if response.status_code == 200:
            try:
                warehouses:dict = response.json()["response"][productID]["warehouses"]
            except:
                return None
            
            warehouseid_dict:dict= warehouses.get(warehouseID)
            if(warehouseid_dict):
                return warehouseid_dict.get("inStock")
            return "not provided"
        else:
            error_log(f"getting error response in get availability. response code: {response.status_code}, response text: {response.text}")
            return None
            
    def write_stock_correction(self, productID:str, warehouseID:str, locationID:int, qty:int, cost:int|float)->None|str:
        url = f"{self.base_url}/warehouse-service/warehouse/{warehouseID}/stock-correction"
        try:
            productID_int = int(productID)
        except:
            return f"Could not convert productID to int. product id: {productID}"
        payload = json.dumps({
            "corrections": [{
                "quantity": qty,
                "productId": productID_int,
                "reason": "Stock correction",
                "locationId": locationID,
                "cost": {
                    "currency": "NOK",
                    "value": cost
                }

            }]
        })
        try:
            response = requests.post(url=url, headers=self.headers, timeout=self.timeout, data=payload)
        except TimeoutError as e:
            return f"Timeout error : {repr(e)}"
        except Exception as e:
            return f"Failed getting a response, error : {repr(e)}"
            
        if response.status_code == 200:
            return None
        else:
            return f"Error sending the post request status code: {response.status_code}. Response text: {response.text}"


def strip_letter_prefix(s:str) -> str:
    pattern = r'^[A-Za-z]+-'
    return re.sub(pattern, '', s)


def match_sku(file_name:str, sku:str) -> dict|str:
    with open(f'{file_name}.json', 'r') as file:
        data:list[dict] = json.load(file)
        striped_sku:str = strip_letter_prefix(sku)
        for ele in data:
            file_sku = ele.get("sku")
            if file_sku is not None:
                if striped_sku == strip_letter_prefix(file_sku):
                    return ele
        return sku


def convert_to_int(str_num:str) -> int|None:
    try:
        num = int(str_num)
        return num
    except:
        return None


def convert_to_float(str_num:str) -> float|None:
    try:
        num = float(str_num)
        return num
    except:
        return None



def append_list_to_json(list_data:list, json_file_path:str) -> None:
    if not list_data:
        return

    json_data = []

    if os.path.exists(json_file_path) and os.path.getsize(json_file_path) > 0:
        try:
            with open(json_file_path, 'r') as file:
                json_data = json.load(file)
        except json.JSONDecodeError:
            error_log(f"Error reading {json_file_path}. File might be corrupted.")
            return

    json_data.append(list_data)

    try:
        with open(json_file_path, 'w') as file:
            json.dump(json_data, indent=4)
        print(f"Successfully appended list to {json_file_path}")
    except Exception as e:
        error_log(f"Error writing to file: {repr(e)}")

    
locationID = 19
warehouseID = "10"
    
if __name__ == "__main__":
    vb_data = VikingBadStock().get_stock()
    not_found_sku = []
    for vb_product in vb_data:
        vb_sku:str = vb_product.get("sku")
        matched_sku:dict|str = match_sku("vbproducts", vb_sku)

        if isinstance(matched_sku, str):
            not_found_sku.append(matched_sku)
            continue
        
        
        vb_stock:dict|None = vb_product.get("stock")
        if vb_stock is None:
            error_log("error in vb product: ", vb_product)
            continue
        
        vb_available:str|None = vb_stock.get("available")
        if vb_available is None:
            debug_log(f"vb_available is none for: {vb_product}")
            continue
            
        vb_available_int:int|None = convert_to_int(vb_available)
        if vb_available is None:
            error_log(f"value error in converting available to int in: {vb_product}")
            continue

        productID:str = matched_sku.get("productErpId")
        inStock:int|None|str = BrightpearlStock().get_product_availability(productID=productID, warehouseID=warehouseID)
        if inStock is None:
            error_log(f"brightpearl inStock is None in: {vb_product}")
            continue
        
        if isinstance(inStock, str):
            inStock = 0
        
        if inStock == 0 and vb_available_int < 1:
            debug_log(f"no need for correction for {vb_product} snice both inStock and vb_available = 0")
            continue
            
        intern_sku:str = matched_sku.get("sku")
        cost:float = convert_to_float(matched_sku.get("costPrice"))
        
        if inStock == vb_available_int:
            debug_log(f"no need for correction for {vb_product} snice both inStock and vb_available equal, inStock: {inStock}, vb_available: {vb_available}")
    
        if inStock > vb_available_int:
            qty = inStock-vb_available_int
            debug_log(f"preforming correction for productid: {productID} with qty: {qty}")
            result:None|str = BrightpearlStock().write_stock_correction(
                productID=productID,
                warehouseID=warehouseID,
                locationID=locationID,
                qty=qty,
                cost=cost
            )
            if result is not None:
                error_log(result)
                
        if inStock < vb_available_int:
            qty = vb_available_int-inStock
            debug_log(f"preforming correction for productid: {productID} with qty: {qty}")
            result:None|str = BrightpearlStock().write_stock_correction(
                productID=productID,
                warehouseID=warehouseID,
                locationID=locationID,
                qty=qty,
                cost=cost
            )
            if result is not None:
                error_log(result)
        
    append_list_to_json(list_data=not_found_sku, json_file_path="notfoundsku.json")