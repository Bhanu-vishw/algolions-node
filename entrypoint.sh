#!/bin/bash
set -e

export NODE_WALLET_PATH=${NODE_WALLET_PATH:-/nodes/wallet.json}
export NODE_CONFIG_PATH=${NODE_CONFIG_PATH:-/nodes/node_config.json}
export ABI_PATH=${ABI_PATH:-/nodes/JobLogger.json}

echo "🟢 [Node Entrypoint] Starting Micro Aladdin Node onboarding..."

if [ ! -f "$NODE_WALLET_PATH" ] || [ ! -f "$NODE_CONFIG_PATH" ]; then
    echo "🔧 [Setup] Wallet/config missing — running setup_node.py"
    python3 /nodes/algolions_node/setup_node.py --wallet "$NODE_WALLET_PATH" --config "$NODE_CONFIG_PATH"
fi

echo "✅ [Setup] Wallet/config ready!"
exec python3 /nodes/algolions_node/node.py --wallet "$NODE_WALLET_PATH" --config "$NODE_CONFIG_PATH" --abi "$ABI_PATH"
