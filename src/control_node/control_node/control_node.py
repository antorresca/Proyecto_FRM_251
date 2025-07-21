import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient

from std_msgs.msg import Float32, String
from geometry_msgs.msg import Point
from std_srvs.srv import Empty
from hexapod_interfaces.srv import ObtenerPoseRobot
from hexapod_interfaces.action import EnviarPaso

from math import cos, sin, atan2, sqrt, radians, degrees
import numpy as np


class ControlNode(Node):
    def __init__(self):
        super().__init__('control_node')

        self._action_client = ActionClient(self, EnviarPaso, 'gui_action')
        self.cli_pose = self.create_client(ObtenerPoseRobot, 'get_orientacion_robot')
        self.cli_siguiente_objetivo = self.create_client(Empty, 'siguiente_objetivo')  # ← nuevo cliente

        self.subscription = self.create_subscription(Point, 'trayectoria', self.recibir_objetivo, 10)
        self.srv_activar = self.create_service(Empty, 'activar_control', self.callback_activar)

        self.activado = False
        self.pose = None
        self.objetivo = None

        self.tolerancia_dist = 0.2
        self.tolerancia_ang = radians(12)
        self.avance_dist = 12.0
        self.giro_angulo = radians(10)

    def recibir_objetivo(self, msg):
        self.objetivo = np.array([msg.x, msg.y])
        self.get_logger().info(f"Objetivo recibido: {self.objetivo}")
        self.ejecutar_control()

    def callback_activar(self, request, response):
        self.get_logger().info("Activación recibida. Ejecutando ciclo de control.")
        self.activado = True
        self.ejecutar_control()
        return response

    def ejecutar_control(self):
        if self.objetivo is None:
            self.get_logger().warn("No hay objetivo definido.")
            self.activado = False
            return

        if not self.cli_pose.wait_for_service(timeout_sec=1.0):
            self.get_logger().error("Servicio get_orientacion_robot no disponible.")
            self.activado = False
            return

        request = ObtenerPoseRobot.Request()
        future = self.cli_pose.call_async(request)
        future.add_done_callback(self.procesar_pose)

    def procesar_pose(self, future):
        try:
            result = future.result()
            x = result.x
            y = result.y
            angle_deg = result.angle
            self.pose = (np.array([x, y]), radians(angle_deg))

            paso = self.calcular_paso(self.pose[0], self.pose[1], self.objetivo)

            if paso is not None:
                self.enviar_paso(paso)
            else:
                self.get_logger().info("Objetivo alcanzado.")
                self.llamar_siguiente_objetivo()  # ← llamar siguiente objetivo
        except Exception as e:
            self.get_logger().error(f"Error al procesar pose: {e}")
        finally:
            self.activado = False

    def calcular_paso(self, pos_movil, theta_movil, punto_objetivo_global):
        R_movil = np.array([
            [cos(theta_movil), -sin(theta_movil)],
            [sin(theta_movil),  cos(theta_movil)]
        ])
        punto_local = R_movil.T @ (punto_objetivo_global - pos_movil)
        distancia = np.linalg.norm(punto_local)
        angulo = atan2(punto_local[1], punto_local[0])

        self.get_logger().info(f"Distancia={distancia:.2f}, Ángulo={degrees(angulo):.2f}°")

        if abs(angulo) > self.tolerancia_ang:
            return 2 if angulo > 0 else 3
        elif distancia > self.tolerancia_dist:
            return 1
        else:
            return None

    def enviar_paso(self, paso):
        if not self._action_client.wait_for_server(timeout_sec=1.0):
            self.get_logger().error("No se encuentra el servidor de acción 'gui_action'")
            return

        goal_msg = EnviarPaso.Goal()
        goal_msg.paso = paso
        self.get_logger().info(f"Enviando paso: {paso}")
        send_goal_future = self._action_client.send_goal_async(goal_msg)
        send_goal_future.add_done_callback(self.goal_response_callback)

    def goal_response_callback(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().warn('Paso rechazado')
            return
        self.get_logger().info('Paso aceptado')
        goal_handle.get_result_async().add_done_callback(self.result_callback)

    def result_callback(self, future):
        result = future.result().result
        self.get_logger().info(f"Resultado de paso: recibido={result.recibido}")

    def llamar_siguiente_objetivo(self):  # ← nuevo método
        if not self.cli_siguiente_objetivo.wait_for_service(timeout_sec=1.0):
            self.get_logger().warn("Servicio 'siguiente_objetivo' no disponible.")
            return

        request = Empty.Request()
        future = self.cli_siguiente_objetivo.call_async(request)
        future.add_done_callback(self.callback_siguiente_objetivo)

    def callback_siguiente_objetivo(self, future):  # ← nuevo callback
        try:
            future.result()
            self.get_logger().info("Solicitud de siguiente objetivo enviada correctamente.")
        except Exception as e:
            self.get_logger().error(f"Error al solicitar siguiente objetivo: {e}")


def main(args=None):
    rclpy.init(args=args)
    node = ControlNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
