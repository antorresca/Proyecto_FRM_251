from setuptools import setup
import os
from glob import glob

package_name = 'control_node'

setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name), glob('launch/*.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Your Name',
    maintainer_email='you@example.com',
    description='Nodo de control que comunica con GUI usando acción',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'control_node = control_node.control_node:main',
        ],
    },
)
