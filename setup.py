from setuptools import setup, find_packages

setup(
    name="Web Glacier",
    version="1.0",
    long_description="A simple web front-end for interfacing with Amazon Glacier.  The information about what is stored on Amazon's servers is stored locally in a database.",
    inclued_package_data=True,
    zip_safe=False,
    install_requires=[
      "Flask",
      "flask-sqlalchemy",
      "boto",
      "mysql-python"
      ],
    packages=find_packages()
    )
