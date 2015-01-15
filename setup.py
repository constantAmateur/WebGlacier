from setuptools import setup, find_packages

setup(
    name="WebGlacier",
    version="0.3.8.alpha",
    long_description="A simple web front-end for interfacing with Amazon Glacier.",
    inclued_package_data=True,
    zip_safe=False,
    install_requires=[
      "Flask",
      "flask-sqlalchemy",
      "flask-wtf",
      "boto"
      ],
    packages=find_packages()
    )
