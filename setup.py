"""
Package shellfoundry_traffic for distribution.
"""

from setuptools import find_packages, setup


def main() -> None:
    """Packaging business logic."""
    with open("requirements.txt") as requirements:
        install_requires = requirements.read().splitlines()
    with open("README.md") as readme:
        long_description = readme.read()

    setup(
        name="shellfoundry-traffic",
        url="https://github.com/QualiSystems/shellfoundry-traffic",
        use_scm_version={
            "root": ".",
            "relative_to": __file__,
            "local_scheme": "node-and-timestamp",
        },
        license="Apache Software License",
        author="QualiSystems",
        author_email="info@qualisystems.com",
        long_description=long_description,
        platforms="any",
        install_requires=install_requires,
        packages=find_packages(include=["shellfoundry*"]),
        include_package_data=True,
        entry_points={"console_scripts": ["shellfoundry_traffic = shellfoundry_traffic.shellfoundry_traffic_cmd:main"]},
        classifiers=[
            "Development Status :: 5 - Production/Stable",
            "Natural Language :: English",
            "Topic :: Software Development :: Testing :: Traffic Generation",
            "Intended Audience :: Developers",
            "License :: OSI Approved :: Apache Software License",
            "Operating System :: OS Independent",
            "Programming Language :: Python :: 3.7",
        ],
    )


if __name__ == "__main__":
    main()
