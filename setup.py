from setuptools import setup, find_packages

setup(
    name="research-mode",
    version="1.0.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "pydicom>=2.4.0",
        "numpy>=1.24.0",
        "Pillow>=10.0.0",
        "pytest>=7.4.0",
        "python-dateutil>=2.8.0",
    ],
    entry_points={
        "console_scripts": [
            "research-mode=research_mode.cli:main",
        ],
    },
)
