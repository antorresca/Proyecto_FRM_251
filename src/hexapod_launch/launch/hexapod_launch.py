from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='dynamixel_node',
            executable='dynamixel_node',
            name='dynamixel',
            output='screen'
        ),
        Node(
            package='gripper_node',
            executable='gripper_node',
            name='gripper',
            output='screen',
            arguments=['--ros-args', '--log-level', 'fatal']
        )
    ])