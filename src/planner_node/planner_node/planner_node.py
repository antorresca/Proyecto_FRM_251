import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Point
from hexapod_interfaces.srv import ObtenerObjetos
from std_srvs.srv import Empty, Trigger

class PlannerNode(Node):
    def __init__(self):
        super().__init__('planner_node')

        self.publisher = self.create_publisher(Point, '/trayectoria', 10)
        self.cli = self.create_client(ObtenerObjetos, 'get_objetos_detectados')
        self.srv = self.create_service(Empty, 'siguiente_objetivo', self.callback_siguiente_objetivo)
        self.gripper_cli = self.create_client(Trigger, 'activar_gripper')

        self.objetos_ordenados = []
        self.indice_actual = 0
        self.estado = 'objetivo'
        self.ultimo_color = None
        self.ultimo_punto_publicado = None  # NUEVO: almacena el último punto publicado
        self.esperando_objetos = False

        self.zonas = {
            0: Point(x=0.160, y=0.250, z=0.0),
            1: Point(x=0.160, y=0.850, z=0.0),
        }

        self.get_logger().info('planner_node listo')
        self.elegir_objetivo()

    def elegir_objetivo(self):
        if self.esperando_objetos:
            return

        if not self.cli.wait_for_service(timeout_sec=1.0):
            self.get_logger().warn('Servicio "get_objetos_detectados" no disponible')
            return

        self.get_logger().info('Solicitando lista de objetos...')
        req = ObtenerObjetos.Request()
        future = self.cli.call_async(req)
        future.add_done_callback(self.callback_respuesta)
        self.esperando_objetos = True

    def callback_respuesta(self, future):
        self.esperando_objetos = False
        try:
            res = future.result()
            if len(res.objetos) == 0:
                self.get_logger().info('No se detectaron objetos')
                return

            objetos_filtrados = [o for o in res.objetos if o.x > 0.3 and o.color in [0, 1]]
            if not objetos_filtrados:
                self.get_logger().info('No hay objetos válidos (x > 0.3 y color 0 o 1)')
                return

            objetos = sorted(objetos_filtrados, key=lambda o: o.x)
            objetos_por_color = {}
            for obj in objetos:
                objetos_por_color.setdefault(obj.color, []).append(obj)

            self.objetos_ordenados = []
            for color in sorted(objetos_por_color.keys()):
                self.objetos_ordenados.extend(objetos_por_color[color])

            self.indice_actual = 0
            self.estado = 'objetivo'
            self.publicar_siguiente()

        except Exception as e:
            self.get_logger().error(f'Error en callback: {e}')

    def callback_siguiente_objetivo(self, request, response):
        if self.estado == 'zona':
            self.indice_actual += 1
            self.estado = 'objetivo'
        else:
            self.estado = 'zona'

        self.publicar_siguiente()
        return response

    def publicar_siguiente(self):
        punto = None

        if self.estado == 'objetivo':
            if self.indice_actual < len(self.objetos_ordenados):
                obj = self.objetos_ordenados[self.indice_actual]
                punto = Point(x=obj.x, y=obj.y, z=0.0)
                self.get_logger().info(f'Objeto seleccionado: x={obj.x:.2f}, y={obj.y:.2f}, color={obj.color}')
                self.ultimo_color = obj.color
            else:
                self.get_logger().info('No hay más objetos disponibles. Reintentando detección...')
                self.elegir_objetivo()
                return

        elif self.estado == 'zona':
            if self.ultimo_color in self.zonas:
                punto = self.zonas[self.ultimo_color]
                self.get_logger().info(f'Zona seleccionada para color {self.ultimo_color}')
            else:
                self.get_logger().warn('Color desconocido, no se puede enviar zona.')
                return

        # Verifica si el punto ya fue publicado
        if self.ultimo_punto_publicado and \
           abs(self.ultimo_punto_publicado.x - punto.x) < 1e-3 and \
           abs(self.ultimo_punto_publicado.y - punto.y) < 1e-3:
            self.get_logger().warn('Punto ya fue publicado, evitando duplicado.')
            return

        # Publica si es diferente
        self.publisher.publish(punto)
        self.ultimo_punto_publicado = punto  # Actualiza el último punto
        self.activar_gripper()

    def activar_gripper(self):
        if not self.gripper_cli.wait_for_service(timeout_sec=1.0):
            self.get_logger().warn('Servicio "activar_gripper" no disponible')
            return

        req = Trigger.Request()
        future = self.gripper_cli.call_async(req)
        future.add_done_callback(self.callback_gripper)

    def callback_gripper(self, future):
        try:
            res = future.result()
            if res.success:
                self.get_logger().info('Gripper activado correctamente')
            else:
                self.get_logger().warn(f'Fallo al activar gripper: {res.message}')
        except Exception as e:
            self.get_logger().error(f'Error al activar gripper: {e}')

def main(args=None):
    rclpy.init(args=args)
    node = PlannerNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
