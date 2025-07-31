from setuptools import setup, find_packages

setup(
    name="algolions_node",  # <-- THIS IS THE ONLY NAME!
    version="0.1.0",
    packages=find_packages(),
    install_requires=["requests", "eth-account"],
    entry_points={
        "console_scripts": [
            "algolions-node=algolions_node.node:main",
            "algolions-node-setup=algolions_node.setup_node:main"
        ]
    },
    description="Algolions Decentralized Node Client",
    author="Bhanu Vishwakarma",
    author_email="rickstane6@email.com",
)
