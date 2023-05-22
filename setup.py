from setuptools import setup

setup(
    name="kite",
    version="0.1.0",
    py_modules=["kite"],
    install_requires=[
        "Click",
    ],
    entry_points={
        "console_scripts": [
            "kite = kite:kite",
        ],
    },
)
