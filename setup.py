from setuptools import setup, find_packages

setup(
    name="youtube-data-backend",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "google-api-python-client",
        "cachetools",
        "prometheus-client",
        "flask",
        "flask-cors",
    ],
    extras_require={
        "dev": [
            "pytest",
            "pytest-asyncio",
            "pytest-cov",
        ]
    },
)