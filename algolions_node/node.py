import requests
import json
import os
import time
import hashlib
import subprocess
import shutil
import random
from datetime import datetime
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
import platform
import threading
import socket

CONFIG_FILE = "node_config.json"

RANDOM_POLL_MIN = float(os.environ.get("RANDOM_POLL_MIN", 5))
RANDOM_POLL_MAX = float(os.environ.get("RANDOM_POLL_MAX", 11))
RANDOM_CLAIM_MIN = float(os.environ.get("RANDOM_CLAIM_MIN", 0))
RANDOM_CLAIM_MAX = float(os.environ.get("RANDOM_CLAIM_MAX", 3))

OUTPUT_SIZE_LIMIT = 100 * 1024 * 1024  # 100 MB

def log(msg, level="INFO"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    color = {"INFO": "\033[92m", "WARN": "\033[93m", "ERR": "\033[91m", "READY": "\033[96m"}
    print(f"{color.get(level, '')}[{now}][{level}] {msg}\033[0m", flush=True)

# --- FAIL JOB: Always call with executor=wallet ---
def fail_job(api_base, job_id, reason, error_code=1, executor=None):
    try:
        requests.post(
            f"{api_base}/fail-job/",
            data={
                "job_id": job_id,
                "reason": reason,
                "errorCode": error_code,
                "executor": executor   # <-- Always the node wallet!
            },
            timeout=15
        )
        log(f"Successfully notified backend of failure for job {job_id} (executor={executor})", "INFO")
    except Exception as e:
        log(f"Failed to notify backend of job failure for job {job_id}: {e}", "ERR")

def load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)

def download_ipfs(cid, out_path):
    try:
        url = f"https://ipfs.io/ipfs/{cid}"
        r = requests.get(url, timeout=60)
        if r.ok:
            with open(out_path, "wb") as f:
                f.write(r.content)
            return True
        log(f"IPFS download failed: {cid}", "WARN")
        return False
    except Exception as e:
        log(f"Error downloading from IPFS: {e}", "ERR")
        return False

def robust_post(url, data=None, files=None, headers=None, max_attempts=3, delay=3):
    attempt = 0
    while attempt < max_attempts:
        try:
            r = requests.post(url, data=data, files=files, headers=headers, timeout=15)
            if r.ok:
                return r
            log(f"Backend update failed ({r.status_code}): {r.text.strip()}", "WARN")
        except requests.RequestException as e:
            log(f"Backend POST error: {e}", "WARN")
        attempt += 1
        time.sleep(delay * attempt)
    return None

def submit_job_result(api_base, job_id, wallet, result_path, api_key=None):
    url = f"{api_base}/api/submit-result/"
    with open(result_path, "rb") as rf:
        files = {"result_file": (os.path.basename(result_path), rf)}
        data = {"job_id": job_id, "wallet_address": wallet}
        headers = {"x-api-key": api_key} if api_key else None
        r = robust_post(url, data=data, files=files, headers=headers)
        if r and r.ok:
            log(f"Result uploaded for job {job_id}.", "INFO")
            return True
        log(f"Failed to upload result for job {job_id} after retries.", "ERR")
        return False

def update_executor_in_questdb(api_base, job_id, wallet_address, api_key=None):
    url = f"{api_base}/update-job-executor/"
    data = {"job_id": job_id, "wallet_address": wallet_address}
    headers = {"x-api-key": api_key} if api_key else None
    r = robust_post(url, data=data, headers=headers)
    if r and r.status_code == 200:
        log(f"Executor for job {job_id} updated in QuestDB.", "INFO")
        return True
    else:
        log(f"Error updating executor in QuestDB for job {job_id}.", "ERR")
        return False

def update_tx_hash_in_backend(api_base, job_id, tx_hash, api_key=None):
    url = f"{api_base}/api/update-tx-hash/"
    data = {"job_id": job_id, "tx_hash": tx_hash}
    headers = {"x-api-key": api_key} if api_key else None
    r = robust_post(url, data=data, headers=headers)
    if r and r.status_code == 200:
        log(f"Transaction hash for job {job_id} updated in backend.", "INFO")
        return True
    else:
        log(f"Error updating tx hash in backend for job {job_id}.", "ERR")
        return False

def fail_job_onchain(web3, contract, chain_job_id, reason, error_code, wallet, pk, api_base, job_id):
    try:
        nonce = web3.eth.get_transaction_count(wallet)
        tx = contract.functions.failJob(chain_job_id, reason, error_code).build_transaction({
            "from": wallet, "nonce": nonce, "gas": 300000, "gasPrice": web3.eth.gas_price
        })
        signed_tx = web3.eth.account.sign_transaction(tx, private_key=pk)
        tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
        web3.eth.wait_for_transaction_receipt(tx_hash)
        log(f"Job {chain_job_id + 1} failJob called on-chain, tx hash: {tx_hash.hex()}", "ERR")
        # --- Always update backend QuestDB as well ---
        return tx_hash.hex()
    except Exception as e:
        log(f"Failed to call failJob on-chain for job {chain_job_id + 1}: {e}", "ERR")
        return None

def get_result_hash(filepath):
    with open(filepath, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()  # 64-char hex string

def get_node_info(config):
    node_id = config["node_id"]
    country = config.get("country", "N/A")
    hardware = config.get("hardware", "N/A")
    status = "active"
    return node_id, country, hardware, status

def send_heartbeat_periodically(node_id, country, hardware, status, uptime_fn, api_base):
    def heartbeat():
        payload = {
            "node_id": node_id,
            "country": country,
            "hardware": hardware,
            "status": status,
            "uptime": uptime_fn(),
        }
        try:
            requests.post(f"{api_base}/api/network/heartbeat", json=payload, timeout=5)
        except Exception as e:
            print(f"[WARN] Heartbeat failed: {e}")
        threading.Timer(60, heartbeat).start()  # Every 60 seconds
    heartbeat()

# --- Robust reward withdrawal util (add near your log utilities) ---

def check_node_eligibility(api_base, node_id):
    try:
        url = f"{api_base}/api/node-eligibility/{node_id}"
        r = requests.get(url, timeout=10)
        if r.ok:
            data = r.json()
            return data.get("eligible", False), data
        else:
            return False, {"error": "Eligibility API error", "msg": r.text}
    except Exception as e:
        return False, {"error": "Eligibility check failed", "msg": str(e)}

def try_withdraw_rewards(contract, web3, wallet, private_key, max_attempts=5, delay=2):
    for attempt in range(1, max_attempts + 1):
        try:
            nonce = web3.eth.get_transaction_count(wallet)
            tx = contract.functions.withdrawRewards().build_transaction({
                "from": wallet,
                "nonce": nonce,
                "gas": 200_000,
                "gasPrice": web3.eth.gas_price,
            })
            signed_tx = web3.eth.account.sign_transaction(tx, private_key=private_key)
            # Try both attribute names for compatibility
            raw_tx = getattr(signed_tx, 'rawTransaction', None) or getattr(signed_tx, 'raw_transaction', None)
            if raw_tx is None:
                raise AttributeError(f"SignedTransaction has no 'rawTransaction' or 'raw_transaction'. Found: {dir(signed_tx)}")
            tx_hash = web3.eth.send_raw_transaction(raw_tx)
            web3.eth.wait_for_transaction_receipt(tx_hash)
            log(f"✅ Rewards withdrawal succeeded! TX: {tx_hash.hex()}", "READY")
            return True
        except Exception as e:
            if attempt == max_attempts:
                log(f"Reward withdrawal ultimately failed after {max_attempts} attempts: {e}", "WARN")
            else:
                log(f"Withdraw attempt {attempt} failed: {e} (retrying in {delay} sec)", "WARN")
                time.sleep(delay)
                delay = min(delay * 2, 30)
    return False


def main():
    config = load_config()
    wallet, pk, api_base, eth_node_url, contract_address, abi_path = (
        config["wallet_address"], config["private_key"], config["api_base"],
        config["eth_node_url"], config["contract_address"], config["abi_path"]
    )
    api_key = config.get("api_key")  # Optional

    with open(abi_path) as f:
        abi = json.load(f)["abi"]

    web3 = Web3(Web3.HTTPProvider(eth_node_url))
    web3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    contract = web3.eth.contract(address=web3.to_checksum_address(contract_address), abi=abi)

    log(f"Node wallet: {wallet}", "INFO")
    log(f"API base: {api_base}", "INFO")

    # -------- Heartbeat setup ---------
    node_id, country, hardware, status = get_node_info(config)
    start_time = time.time()
    def get_uptime():
        return round(time.time() - start_time, 2)
    send_heartbeat_periodically(node_id, country, hardware, status, get_uptime, api_base)
    # ----------------------------------

    while True:
        try:
            jobs = requests.get(f"{api_base}/api/unclaimed-jobs").json()
        except Exception as e:
            log(f"API error: {e}", "ERR")
            poll_delay = random.uniform(RANDOM_POLL_MIN, RANDOM_POLL_MAX)
            log(f"Waiting {poll_delay:.2f}s before next poll (randomized)", "INFO")
            time.sleep(poll_delay)
            continue

        for job in jobs:
            job_id = job["job_id"]
            chain_job_id = job.get("chain_job_id")
            if chain_job_id is None:
                log(f"Job {job_id} has no chain_job_id! Skipping.", "ERR")
                continue

            try:
                job_count = contract.functions.jobCount().call()
                if chain_job_id < 0 or chain_job_id >= job_count:
                    log(f"Job {job_id} skipped: on-chain job index {chain_job_id} out of range [0, {job_count-1}]", "WARN")
                    continue
            except Exception as e:
                log(f"Could not fetch jobCount from contract: {e}", "ERR")
                continue

            try:
                job_struct = contract.functions.jobs(chain_job_id).call()
            except Exception as e:
                log(f"On-chain fetch failed for job {job_id} (on-chain idx {chain_job_id}): {e}", "WARN")
                continue

            on_chain_status = job_struct[9]
            if on_chain_status != 0:
                log(f"Job {job_id} skipped: status is not 'Submitted' (status={on_chain_status})", "INFO")
                continue

            # Claim on-chain (with improved error handling)
            delay = random.uniform(RANDOM_CLAIM_MIN, RANDOM_CLAIM_MAX)
            if delay > 0:
                log(f"Waiting {delay:.2f}s before claiming job {chain_job_id+1} (randomized)...", "INFO")
                time.sleep(delay)
            try:
                nonce = web3.eth.get_transaction_count(wallet)
                tx = contract.functions.claimJob(chain_job_id).build_transaction({
                    "from": wallet, "nonce": nonce, "gas": 500000, "gasPrice": web3.eth.gas_price
                })
                signed_tx = web3.eth.account.sign_transaction(tx, private_key=pk)
                tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
                web3.eth.wait_for_transaction_receipt(tx_hash)
                log(f"Job {chain_job_id + 1} claimed on-chain, tx hash: {tx_hash.hex()}", "READY")
                update_tx_hash_in_backend(api_base, job_id, tx_hash.hex(), api_key)
                update_executor_in_questdb(api_base, job_id, wallet, api_key)
            except Exception as e:
                if hasattr(e, 'args') and len(e.args) > 0 and "Job unavailable" in str(e.args[0]):
                    log(f"Job {chain_job_id + 1} unavailable, skipping. (Another node may have claimed it)", "WARN")
                    continue
                else:
                    log(f"On-chain claim failed for job {chain_job_id + 1}: {e}", "ERR")
                    continue

            try:
                requests.post(f"{api_base}/claim-job/", data={"job_id": job_id, "wallet_address": wallet})
            except Exception as e:
                log(f"Backend claim-job failed: {e}", "WARN")

            log(f"Job {job_id} claimed. Running model...", "INFO")

            sandbox = os.path.join("sandbox", f"{job_id}_{int(time.time())}")
            os.makedirs(sandbox, exist_ok=True)
            try:
                model_path = os.path.join(sandbox, "model.py")
                data_path = os.path.join(sandbox, "data.csv")
                output_path = os.path.join(sandbox, f"result_{job_id}.txt")

                # --- Download model.py from IPFS ---
                if not download_ipfs(job["model_cid"], model_path):
                    log(f"Failed to download model.py for job {job_id}", "WARN")
                    fail_job_onchain(web3, contract, chain_job_id, "Model download failed", 2, wallet, pk, api_base, job_id)
                    fail_job(api_base, job_id, "Model download failed", 2, executor=wallet)
                    continue

                # --- Download dataset.csv from IPFS ---
                if not download_ipfs(job["dataset_cid"], data_path):
                    log(f"Failed to download data.csv for job {job_id}", "WARN")
                    fail_job_onchain(web3, contract, chain_job_id, "Dataset download failed", 3, wallet, pk, api_base, job_id)
                    fail_job(api_base, job_id, "Dataset download failed", 3, executor=wallet)
                    continue

                # --- Execute model.py ---
                exec_result = subprocess.run(
                    ["python", model_path, data_path, output_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=900  # 15 min
                )
                if exec_result.returncode != 0:
                    log(f"Job execution failed for job {job_id}", "ERR")
                    fail_job_onchain(web3, contract, chain_job_id, "Execution failed", 1, wallet, pk, api_base, job_id)
                    fail_job(api_base, job_id, "Execution failed", 1, executor=wallet)
                    continue

                # --- OUTPUT SIZE CHECK ---
                if os.path.exists(output_path):
                    if os.path.getsize(output_path) > OUTPUT_SIZE_LIMIT:
                        os.remove(output_path)
                        log(f"Output for job {job_id} exceeded {OUTPUT_SIZE_LIMIT // (1024*1024)}MB! Marking as failed.", "ERR")
                        fail_job_onchain(web3, contract, chain_job_id, "Output file exceeded size limit", 4, wallet, pk, api_base, job_id)
                        fail_job(api_base, job_id, "Output file exceeded size limit", 4, executor=wallet)
                        continue

                # --- SUBMIT FINALIZATION ON-CHAIN FROM NODE ---
                result_hash = get_result_hash(output_path)
                if isinstance(result_hash, str):
                    result_hash_bytes32 = bytes.fromhex(result_hash)
                else:
                    result_hash_bytes32 = result_hash
                nonce = web3.eth.get_transaction_count(wallet)
                tx = contract.functions.completeJob(chain_job_id, result_hash_bytes32).build_transaction({
                    "from": wallet, "nonce": nonce, "gas": 300000, "gasPrice": web3.eth.gas_price
                })
                signed_tx = web3.eth.account.sign_transaction(tx, private_key=pk)
                tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
                web3.eth.wait_for_transaction_receipt(tx_hash)
                log(f"Job {job_id} completeJob called on-chain, tx hash: {tx_hash.hex()}", "READY")
                update_tx_hash_in_backend(api_base, job_id, tx_hash.hex(), api_key)

                # Optionally POST result to backend for record/log
                submit_job_result(api_base, job_id, wallet, output_path, api_key)
                log(f"Job {job_id} result uploaded and finalized!", "READY")

                # --- 💸 Withdraw rewards if paid job, but only if eligible! ---
                job_struct = contract.functions.jobs(chain_job_id).call()
                is_paid = job_struct.paid if hasattr(job_struct, "paid") else job_struct[12]
                if is_paid:
                    is_eligible, elig_info = check_node_eligibility(api_base, wallet)
                    if is_eligible:
                        try_withdraw_rewards(contract, web3, wallet, pk)
                    else:
                        log(f"Skipping withdraw: not eligible. Reason: {elig_info.get('message', 'Check rating/num_ratings on dashboard.')}", "WARN")
                else:
                    log(f"No rewards to withdraw for job {job_id} (free/unpaid job)", "INFO")

            finally:
                shutil.rmtree(sandbox)

        poll_delay = random.uniform(RANDOM_POLL_MIN, RANDOM_POLL_MAX)
        time.sleep(poll_delay)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\033[96m[EXIT] Micro Aladdin Node has been shut down safely. 🦁✨\033[0m")
