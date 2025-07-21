import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from std_msgs.msg import String
from std_srvs.srv import Trigger, Empty
from hexapod_interfaces.srv import Activar, SiguientePosicion
from hexapod_interfaces.action import Posicionar
import math

class TransformationNode(Node):
    def __init__(self):
        super().__init__('transformation_node')

        self.ultima_config_publicada = None
        self.flag = False
        self.simulacion = False
        self.n = 0
        self.ejecutando = False  # flag para evitar ejecución simultánea
        self.ultima_posicion = None
        self.repeticiones = 0
        self.max_repeticiones = 2 # Máximo número de veces que se permite recibir la misma posición

        self.cli_action = ActionClient(self, Posicionar, 'posicionar_motores')
        self.cli = self.create_client(SiguientePosicion, 'siguiente_posicion')
        while not self.cli.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('Esperando al servicio siguiente_posicion...')

        self.req = SiguientePosicion.Request()
        self.publisher = self.create_publisher(String, 'joint_values_rad', 10)
        self.srv_reinicio = self.create_service(Trigger, 'reiniciar_trayectoria', self.reiniciar_callback)

        self.srv_activar = self.create_service(Activar, 'activar', self.service_callback)
        self.srv_sim = self.create_service(Trigger, 'modo_simulacion', self.simulacion_callback)
        self.cli_activar = self.create_client(Empty, 'activar_control')

        while not self.cli_activar.wait_for_service(timeout_sec=2.0):
            self.get_logger().warn('Esperando el servicio "activar_control"...')


    def simulacion_callback(self, request, response):
        self.simulacion = not self.simulacion
        response.success = True
        response.message = f"Modo simulación {'activado' if self.simulacion else 'desactivado'}"
        self.get_logger().warn(response.message)
        return response

    def reiniciar_callback(self, request, response):
        self.n = 0
        response.success = True
        response.message = "Índice reiniciado a 0 por cambio de trayectoria"
        self.get_logger().warn(response.message)
        return response


    def service_callback(self, request, response):
        self.flag = request.indicacion
        response.flag = self.flag
        if self.flag:
            self.get_logger().info('Nodo activado. Iniciando trayectoria.')
            self.send_request()
        else:
            self.get_logger().info('Nodo desactivado.')
        return response

    def send_request(self):
        if not self.flag or self.ejecutando:
            return

        self.req.index = self.n
        self.ejecutando = True  # Bloquear nueva ejecución
        future = self.cli.call_async(self.req)
        future.add_done_callback(self.response_callback)

    def response_callback(self, future):
        try:
            response = future.result()  # 👈 Esto debe ir primero

            if response.positions == self.ultima_posicion:
                self.repeticiones += 1
                if self.repeticiones >= self.max_repeticiones:
                    self.get_logger().warn("Posición final repetida múltiples veces. Deteniendo ciclo.")
                    self.flag = False
                    self.ejecutando = False
                    req = Empty.Request()
                    future = self.cli_activar.call_async(req)

                    rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)

                    if future.done():
                        if future.result() is not None:
                            self.get_logger().info("Servicio 'activar' llamado correctamente.")
                        else:
                            self.get_logger().error("Error en la llamada al servicio 'activar'.")
                    else:
                        self.get_logger().error("No se recibió respuesta del servicio 'activar'.")
                    return
            else:
                self.repeticiones = 0
                self.ultima_posicion = response.positions

            data_aux = [
                max(0, min(4095, int(round(2045.0 + ((1028.0 * pos) / 90), 0))))
                for pos in response.positions
            ]
            radianes = [round(math.radians(pos), 2) for pos in response.positions]

            msg_data = ', '.join(map(str, radianes))
            if msg_data != self.ultima_config_publicada:
                msg = String()
                msg.data = msg_data
                self.publisher.publish(msg)
                self.ultima_config_publicada = msg_data
            else:
                self.get_logger().debug("Posición repetida, no se publica.")

            if self.simulacion:
                self.get_logger().warn("Simulación activa: no se envía acción.")
                self.n += 1
                self.ejecutando = False
                self.create_timer(0.5, self.timer_next_step)
                return

            if not self.cli_action.wait_for_server(timeout_sec=1.0):
                self.get_logger().error("Acción 'posicionar_motores' no disponible.")
                self.ejecutando = False
                return

            goal_msg = Posicionar.Goal()
            goal_msg.positions = data_aux
            future_goal = self.cli_action.send_goal_async(goal_msg)
            future_goal.add_done_callback(self.goal_response_callback)

        except Exception as e:
            self.get_logger().error(f"Error al llamar al servicio: {e}")
            self.ejecutando = False

    def timer_next_step(self):
        if self.flag:
            self.send_request()

    def goal_response_callback(self, future_goal):
        goal_handle = future_goal.result()
        if not goal_handle.accepted:
            self.get_logger().error("Acción rechazada.")
            self.ejecutando = False
            return
        self.get_logger().info("Acción aceptada.")
        future_result = goal_handle.get_result_async()
        future_result.add_done_callback(self.result_callback)

    def result_callback(self, future_result):
        try:
            result = future_result.result().result
            if result.flag:
                self.get_logger().info(f"Acción completada. n={self.n}")
                self.n += 1
                self.ejecutando = False
                self.send_request()
            else:
                self.get_logger().error("La acción falló.")
                self.ejecutando = False
        except Exception as e:
            self.get_logger().error(f"Error en la acción: {e}")
            self.ejecutando = False

def main(args=None):
    rclpy.init(args=args)
    node = TransformationNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    rclpy.shutdown()

if __name__ == '__main__':
    main()
