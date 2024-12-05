import requests
import json
import logging
import re
import os
from time import sleep, perf_counter
from dotenv import load_dotenv

# load_dotenv('/home/abkh/nasaFiler/bad/.env.ProdBP')
load_dotenv("/home/allieradm/bad/.env.ProdBP")


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
log_formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S"
)

handler = logging.FileHandler("stocklog.txt")
handler.setFormatter(log_formatter)
logger.addHandler(handler)


def write_log(msg: str, lvl: int) -> None:
    if lvl == 1:
        logger.error(msg)
    if lvl == 2:
        logger.debug(msg)


class VikingBadStock:
    def __init__(self):
        self.base_url = "https://api.vikingbad.no"
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        self.timeout = 10

    def get_stock(self) -> list[dict] | None:
        url = f"{self.base_url}/v0/stock"
        try:
            response = requests.get(url=url, headers=self.headers, timeout=self.timeout)
        except TimeoutError as e:
            write_log(
                f"Timeout error in get stock in vinkingbad stock class : {repr(e)}",
                lvl=1,
            )
            return None
        except Exception as e:
            write_log(
                f"Failed getting a response in get stock in vinkingbad stock class, error : {repr(e)}",
                lvl=1,
            )
            return None

        if response.status_code == 200:
            res: dict[list] = response.json()
            return res.get("data")
        else:
            write_log(
                f"getting error response in get stock in vikingbad. response code: {response.status_code}, response text: {response.text}",
                lvl=1,
            )
            return None


class BrightpearlStock:
    def __init__(self):
        self.base_url = "https://euw1.brightpearlconnect.com/public-api/badnoas"
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "brightpearl-app-ref": os.getenv("PRICE_BP_APP_REFF"),
            "brightpearl-staff-token": os.getenv("PRICE_BP_STAFF_TOKEN"),
        }

        self.timeout = 10

    def get_product_availability(
        self, productID: str, warehouseID: str
    ) -> int | None | str:
        """returns int if there is in stock, None if error, str if inStock not provided in the api data"""
        url = f"{self.base_url}/warehouse-service/product-availability/{productID}"
        try:
            response = requests.get(url=url, headers=self.headers, timeout=self.timeout)
        except TimeoutError as e:
            write_log(f"Timeout error in get availability: {repr(e)}", lvl=1)
            return None
        except Exception as e:
            write_log(
                f"Failed getting a response in get availability, error : {repr(e)}",
                lvl=1,
            )
            return None

        if response.status_code == 200:
            try:
                warehouses: dict = response.json()["response"][productID]["warehouses"]
            except:
                return None

            warehouseid_dict: dict = warehouses.get(warehouseID)
            if warehouseid_dict:
                return warehouseid_dict.get("inStock")
            return "not provided"
        else:
            write_log(
                f"getting error response in get availability. response code: {response.status_code}, response text: {response.text}",
                lvl=1,
            )
            return None

    def write_stock_correction(
        self,
        productID: str,
        warehouseID: str,
        locationID: int,
        qty: int,
        cost: int | float,
    ) -> None | str:
        url = f"{self.base_url}/warehouse-service/warehouse/{warehouseID}/stock-correction"
        try:
            productID_int = int(productID)
        except:
            return f"Could not convert productID to int. product id: {productID}"
        payload = json.dumps(
            {
                "corrections": [
                    {
                        "quantity": qty,
                        "productId": productID_int,
                        "reason": "Stock correction",
                        "locationId": locationID,
                        "cost": {"currency": "NOK", "value": cost},
                    }
                ]
            }
        )
        try:
            response = requests.post(
                url=url, headers=self.headers, timeout=self.timeout, data=payload
            )
        except TimeoutError as e:
            return f"Timeout error : {repr(e)}"
        except Exception as e:
            return f"Failed getting a response, error : {repr(e)}"

        if response.status_code == 200:
            return None
        else:
            return f"Error sending the post request status code: {response.status_code}. Response text: {response.text}"


def strip_letter_prefix(s: str) -> str:
    pattern = r"^[A-Za-z]+-"
    return re.sub(pattern, "", s)


def get_products_data(file_name: str) -> list[dict]:
    with open(f"{file_name}.json", "r") as file:
        return json.load(file)


def match_sku(products_data: list[dict], sku: str) -> dict | str:
    striped_sku: str = strip_letter_prefix(sku)
    for ele in products_data:
        file_sku = ele.get("sku")
        if file_sku is not None:
            if striped_sku == strip_letter_prefix(file_sku):
                return ele
    return sku


def convert_to_int(str_num: str) -> int | None:
    try:
        num = int(str_num)
        return num
    except:
        return None


def convert_to_float(str_num: str) -> float | None:
    try:
        num = float(str_num)
        return num
    except:
        return None


def append_list_to_json(list_data: list, json_file_path: str) -> None:
    if not list_data:
        return

    json_data = []

    if os.path.exists(json_file_path) and os.path.getsize(json_file_path) > 0:
        try:
            with open(json_file_path, "r") as file:
                json_data = json.load(file)
        except json.JSONDecodeError:
            write_log(
                f"Error reading {json_file_path}. File might be corrupted.", lvl=1
            )
            return

    json_data.append(list_data)

    try:
        with open(json_file_path, "w") as file:
            json.dump(json_data, file, indent=4)
    except Exception as e:
        write_log(f"Error writing to file: {repr(e)}", lvl=1)


def calculate_qty(a: int, b: int) -> int:
    difference = b - a
    return difference


def save_products_data(file_name: str, data: list[dict]) -> None:
    with open(f"{file_name}.json", "w") as file:
        json.dump(data, file, indent=4)


def update_cached_availability(
    products_data: list[dict], productID: str, new_value: int
) -> None:
    for product in products_data:
        if product.get("productErpId") == productID:
            product["cachedAvailability"] = new_value
            break


locationID = 19
warehouseID = "10"


def main() -> None:
    vb_data = VikingBadStock().get_stock()
    if vb_data is None:
        write_log(msg="vikingbad data is None breaking out of the loop", lvl=1)
        return

    not_found_sku = []
    products_data = get_products_data(file_name="vbproducts")
    sleep_counter = 0
    for vb_product in vb_data:
        if sleep_counter % 5 == 0:
            sleep(1)
        vb_sku: str = vb_product.get("sku")
        matched_sku: dict | str = match_sku(products_data=products_data, sku=vb_sku)

        if isinstance(matched_sku, str):
            not_found_sku.append(matched_sku)
            continue

        vb_stock: dict | None = vb_product.get("stock")
        if vb_stock is None:
            write_log("error in vb product: ", vb_product, lvl=1)
            continue

        vb_available: str | None = vb_stock.get("available")
        if vb_available is None:
            continue

        vb_available_int: int | None = convert_to_int(vb_available)
        if vb_available is None:
            continue

        productID: str = matched_sku.get("productErpId")
        cached_availanility: int = matched_sku.get("cachedAvailability")

        if cached_availanility == 0 and vb_available_int < 1:
            continue

        if cached_availanility == vb_available_int:
            continue

        else:
            inStock: int | None | str = BrightpearlStock().get_product_availability(
                productID=productID, warehouseID=warehouseID
            )
            if inStock is None:
                write_log(f"brightpearl inStock is None in: {vb_product}", lvl=1)
                inStock = cached_availanility

            if isinstance(inStock, str):
                inStock = 0

            update_cached_availability(
                products_data=products_data,
                productID=productID,
                new_value=vb_available_int,
            )
            cost: float = convert_to_float(matched_sku.get("costPrice"))
            qty: int = calculate_qty(inStock, vb_available_int)
            result: None | str = BrightpearlStock().write_stock_correction(
                productID=productID,
                warehouseID=warehouseID,
                locationID=locationID,
                qty=qty,
                cost=cost,
            )
            sleep_counter += 1
            if result is not None:
                write_log(result, lvl=1)

    save_products_data(file_name="vbproducts", data=products_data)
    append_list_to_json(list_data=not_found_sku, json_file_path="notfoundsku.json")


if __name__ == "__main__":
    start = perf_counter()
    main()
    end = perf_counter()
    elapsed = end - start
    print(f"Time taken: {elapsed:.6f} seconds")
    write_log(
        f"running time is: {elapsed}. another format: {elapsed:.6f} seconds", lvl=1
    )
