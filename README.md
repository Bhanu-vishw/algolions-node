# 🦁 Algolions Node Client (MM Aladdin Node)

This is the official decentralized node client for the Algolions compute network.
Run your own node to process ML jobs, earn rewards, and help power a global, censorship-resistant AI infrastructure.

---

## 🚀 Features

- **Automatic Job Polling:** Continuously polls backend for new unclaimed jobs.
- **Decentralized Execution:** Claims, executes, and completes jobs on-chain using your registered Ethereum wallet.
- **IPFS Integration:** Downloads model/data files from IPFS, uploads results.
- **Secure & Isolated:** Every job runs in a secure, containerized environment.
- **Transparent & Auditable:** Results and payments are tracked both on-chain and off-chain.
- **Fully Configurable:** Wallet, node identity, contract address, API, and more.

---

## 🛠️ Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/Bhanu-vishw/algolions-node.git
cd algolions-node
```

### 2. Prepare Node Configuration

Copy the template config files and fill in your details (do NOT commit secrets to GitHub):

```bash
cp node_config_example.json node_config.json
cp wallet_example.json wallet.json
```

Edit **node_config.json** and **wallet.json** with your wallet address, private key, and node details as instructed by the admin.

### 3. Build and Run the Node with Docker

```bash
# Make sure you have Docker installed and running!

# If you haven't already, create the network (needed for multi-container setups):
docker network create aladdin-net || true

# Build and run your node
docker-compose up --build -d
```

The node will automatically onboard if node_config.json or wallet.json are missing, running an interactive setup in the container.

### 4. Monitor Your Node logs on terminal


### ⚡Manual Install (Advanced/Developers)

For advanced users who want to run without Docker, e.g. for debugging or custom setups.

### 2. Install Requirements

```bash
pip install -r requirements.txt

pip install .
```

### 3. Wallet & Node Setup

Run the setup script (interactive):

```bash
python algolions_node/setup_node.py
```
Or, if installed as a package:

```bash
algolions-node-setup
```
Follow the prompts to create or enter your wallet/private key.

See Below for ref:

1) Generate a new wallet (or enter your existing one).

2) Follow instructions to save your wallet address and private key.

3) Share ONLY your wallet address with the admin for node registration.

4) After registration, you’ll receive a node_config.json to complete your setup.


### 4. Configuration

Edit node_config.json with your wallet, private key, API base, contract address, ABI path and other details as provided by the admin.

json

{
  "wallet_address": "0xYourNodeWallet...",
  "private_key": "0xYourNodePrivateKey...",
  "node_id": "0xYourNodeWallet...",
  "country": "useISOapha2CountryCode",
  "hardware": "youSystemConfig(4 CPU, 16GB RAM)",
  "api_base": "sharedbyAdmin",
  "poll_limit": sharedbyAdmin,
  "abi_path": "JobLogger.json",
  "contract_address": "0xYourJobLoggerContract...",
  "eth_node_url": "sharedbyAdmin"
}

### 🔐 Security

NEVER share your private key!

Only send your wallet address to the admin for registration.

Always keep your private key and wallet.json/node_config.json secure.

### 📝 Troubleshooting

* Missing config or wallet:
The node will prompt you to generate or enter keys the first time.

* Docker errors:
Make sure Docker is running and the aladdin-net network exists.

### 👨‍💻 Author & License

Maintained by Bhanu Vishwakarma
MIT License – see LICENSE for details.
