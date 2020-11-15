"""
Package shellfoundry_traffic for distribution.
"""

from setuptools import setup, find_packages


def main():
    """ Main entry point for setup.py """

    with open('requirements.txt') as f:
        install_requires = f.read().splitlines()
    with open('README.txt') as f:
        long_description = f.read()

    setup(
        name='shellfoundry-traffic',
        url='https://github.com/QualiSystems/shellfoundry-traffic',
        use_scm_version={
            'root': '.',
            'relative_to': __file__,
            'local_scheme': 'node-and-timestamp'
        },
        license='Apache Software License',

        author='QualiSystems',
        author_email='info@qualisystems.com',

        long_description=long_description,

        platforms='any',
        install_requires=install_requires,
        packages=find_packages(exclude=['tests']),
        include_package_data=True,

        entry_points={'console_scripts': ['shellfoundry_traffic = shellfoundry_traffic.shellfoundry_traffic_cmd:main']},

        classifiers=[
            'Development Status :: 5 - Production/Stable',
            'Natural Language :: English',
            'Topic :: Software Development :: Testing :: Traffic Generation',
            'Intended Audience :: Developers',
            'License :: OSI Approved :: Apache Software License',
            'Operating System :: OS Independent',
            'Programming Language :: Python :: 3.7',
        ],
    )


if __name__ == '__main__':
    main()
