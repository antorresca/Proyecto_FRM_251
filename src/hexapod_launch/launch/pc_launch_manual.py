from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='transformation_node',
            executable='transformation_node',
            name='transformation',
            output='screen',
            arguments=['--ros-args', '--log-level', 'fatal']
        ),
        Node(
            package='control_node',
            executable='control_node',
            name='control',
            output='screen',
            #arguments=['--ros-args', '--log-level', 'fatal']
        ),
        Node(
            package='cinematica_node',
            executable='cinematica_node',
            name='cinematica',
            output='screen',
            arguments=['--ros-args', '--log-level', 'fatal']
        ),
        Node(
            package='gui_node',
            executable='gui_client',
            name='gui',
            output='screen'
        ),
        Node(
            package='vision_node',
            executable='vision_node',
            name='vision',
            output='screen',
            arguments=['--ros-args', '--log-level', 'fatal']
        )
    ])