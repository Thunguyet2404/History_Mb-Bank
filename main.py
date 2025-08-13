from flask import Flask, request, jsonify
import requests
import logging
from datetime import datetime, timedelta
import random

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

USERNAME = '' # Sdt Mb Bank  
PASSWORD = '' # Password Mb Bank

LOGIN_API_URL = "http://161.248.178.241:5000/login"
MB_BANK_API_URL = "https://online.mbbank.com.vn/api/retail-transactionms/transactionms/get-account-transaction-history"

DEFAULT_HEADERS = {
    'accept': 'application/json, text/plain, */*',
    'accept-language': 'vi,en-US;q=0.9,en;q=0.8',
    'app': 'MB_WEB',
    'authorization': 'Basic RU1CUkVUQUlMV0VCOlNEMjM0ZGZnMzQlI0BGR0AzNHNmc2RmNDU4NDNm',
    'content-type': 'application/json; charset=UTF-8',
    'origin': 'https://online.mbbank.com.vn',
    'priority': 'u=1, i',
    'referer': 'https://online.mbbank.com.vn/information-account/source-account',
    'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
}

def login(username, password):
    try:
        logging.info(f"Attempting login for user: {username}")
        full_login_url = f"{LOGIN_API_URL}?username={username}&password={password}"
        response = requests.get(full_login_url, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        session_id = data.get('sessionId')
        device_id = data.get('deviceId')

        if not all([session_id, device_id]):
            logging.error(f"Login API response missing credentials for user {username}. Response: {data}")
            return None

        timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')[:16]
        random_part = random.randint(10000, 99999)
        ref_no = f"{username}-{timestamp}-{random_part}"

        return {
            "sessionId": session_id,
            "deviceId": device_id,
            "refNo": ref_no
        }
    except requests.exceptions.RequestException as e:
        logging.error(f"Login failed for user {username}: {e}")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred during login for {username}: {e}")
        return None

@app.route('/get-transaction-history', methods=['GET'])
def get_transaction_history():
    if not USERNAME or not PASSWORD:
        return jsonify({'error': 'Vui lòng điền USERNAME và PASSWORD trong file code.'}), 400
        
    account_no = request.args.get('accountNo')
    if not account_no:
        return jsonify({'error': 'Thiếu accountNo'}), 400

    credentials = login(USERNAME, PASSWORD)
    if not credentials:
        return jsonify({'error': 'Đăng nhập thất bại, vui lòng kiểm tra lại USERNAME/PASSWORD trong code'}), 401

    to_date_str = request.args.get('toDate')
    from_date_str = request.args.get('fromDate')
    try:
        to_date = datetime.strptime(to_date_str, '%d/%m/%Y') if to_date_str else datetime.now()
        from_date = datetime.strptime(from_date_str, '%d/%m/%Y') if from_date_str else to_date - timedelta(days=90)
    except ValueError:
        return jsonify({'error': 'Định dạng ngày không hợp lệ. Sử dụng dd/mm/YYYY.'}), 400

    try:
        payload = {
            'accountNo': account_no,
            'fromDate': from_date.strftime('%d/%m/%Y'),
            'toDate': to_date.strftime('%d/%m/%Y'),
            'sessionId': credentials['sessionId'],
            'refNo': credentials['refNo'],
            'deviceIdCommon': credentials['deviceId']
        }
        headers = DEFAULT_HEADERS.copy()
        headers['deviceid'] = credentials['deviceId']
        headers['elastic-apm-traceparent'] = f'00-ab63e76371611bca76953dc02f6002b0-315bc8f5233d110a-01'
        headers['refno'] = credentials['refNo']
        headers['x-request-id'] = credentials['refNo']

        response = requests.post(
            MB_BANK_API_URL,
            headers=headers,
            json=payload,
            timeout=20
        )

        if response.status_code == 200:
            result = response.json()
            if result and isinstance(result, dict) and result.get('transactionHistoryList') is not None:
                result['transactionHistoryList'] = result.get('transactionHistoryList', [])[:5000]
                return jsonify(result), 200
            else:
                 return jsonify({
                    'error': 'Không tìm thấy danh sách giao dịch',
                    'raw_response': result
                }), 502
        else:
            return jsonify({
                'error': 'MB Bank API trả về lỗi',
                'status_code': response.status_code,
                'response': response.text
            }), response.status_code

    except requests.exceptions.RequestException as e:
        return jsonify({'error': 'Lỗi kết nối tới MB Bank API', 'message': str(e)}), 504
    except Exception as e:
        return jsonify({'error': 'Lỗi nội bộ không xác định', 'message': str(e)}), 500

@app.route('/', methods=['GET'])
def home():
    return jsonify({"message": "Flask API is running. Use /get-transaction-history to fetch data."}), 200

if __name__ == '__main__':
    host = '0.0.0.0'
    port = 5000
    print("--- Flask API is running ---")
    print("Vui lòng điền USERNAME và PASSWORD trong file code trước khi sử dụng.")
    print(f"Example usage:")
    print(f"http://{host}:{port}/get-transaction-history?accountNo=YOUR_ACCOUNT_NO")
    print("--------------------------")
    app.run(host=host, port=port, debug=False)
