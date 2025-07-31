import json
from eth_account import Account
import secrets
import os
import sys

def main():
    print("=" * 55)
    print("      🦁 Micro Aladdin Node Wallet Setup        ")
    print("=" * 55)
    print("You will generate a new Ethereum wallet or use an existing one.")
    print("→ Only share your public wallet address with the admin for node registration.")
    print("→ NEVER share your private key with anyone!\n")

    wallet = input("Enter your registered wallet address (leave blank to generate a new one): ").strip()
    private_key = None

    if not wallet:
        acct = Account.create(secrets.token_hex(32))
        wallet = acct.address
        private_key = acct.key.hex()
        print(f"\n✅ Generated new wallet address: {wallet}")
        print(f"🔑 Private key (copy & keep safe!): {private_key}")
        print("IMPORTANT: Store your private key securely. Losing it means losing access to the node's wallet.\n")
    else:
        private_key = input("Enter the wallet's PRIVATE KEY (never share this with anyone): ").strip()
        if not private_key.startswith("0x"):
            print("ERROR: Private key should start with 0x.")
            sys.exit(1)
        print("\n✅ Wallet address and private key loaded.")

    api_key = input("Enter your Micro Aladdin API key (leave blank if not using): ").strip()

    # NEW: Ask for country
    country = input("Enter your country code (e.g. US, IN, CN): ").strip().upper()
    if not country:
        country = "N/A"

    # NEW: Ask for hardware info (with an example)
    hardware = input("Enter your node hardware info (e.g. '8 vCPU, 32GB RAM, RTX 4090'): ").strip()
    if not hardware:
        hardware = "N/A"

    print("\nNext steps:")
    print("  1. Send ONLY your wallet address to the admin for node registration.")
    print("  2. After the admin registers your address, you will receive a node_config_TEMPLATE.json file.")
    print("  3. Copy your PRIVATE KEY into the provided node_config.json (replace <FILL IN YOURSELF> field).")
    print("  4. Never share your private key with anyone!\n")

    # Optionally, you could write these to a file (wallet.json) for local reference:
    save = input("Save wallet/private key to wallet.json for your reference? (y/N): ").strip().lower()
    if save == "y":
        with open("wallet.json", "w") as f:
            json.dump({"wallet_address": wallet, "private_key": private_key}, f, indent=2)
        print("✅ Saved to wallet.json (do NOT share this file!)")

    # Optionally, save an example node_config.json:
    save_config = input("Save node_config.json template for node? (Y/n): ").strip().lower()
    if save_config in ("", "y", "yes"):
        config = {
            "wallet_address": wallet,
            "private_key": private_key,
            "node_id": wallet,                 # <--- Add node_id = wallet_address
            "country": country,
            "hardware": hardware,
            "api_base": "http://host.docker.internal:8010",
            "poll_limit": 10,
            "abi_path": "JobLogger.json",
            "contract_address": "0x5FbDB2315678afecb367f032d93F642f64180aa3",
            "eth_node_url": "http://host.docker.internal:8545"
        }
        if api_key:
            config["api_key"] = api_key
        with open("node_config.json", "w") as f:
            json.dump(config, f, indent=2)
        print("✅ node_config.json template saved. Edit as needed.")

    print("\nWallet setup complete. 🎉")
    print(f"Your node wallet address: {wallet}")
    print("Keep your private key safe! You will need it to run your node.\n")

if __name__ == "__main__":
    main()
