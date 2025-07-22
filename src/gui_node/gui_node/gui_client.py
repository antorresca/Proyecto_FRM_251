import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient, ActionServer
from hexapod_interfaces.srv import Activar
from hexapod_interfaces.action import Calcular, EnviarPaso
from std_srvs.srv import SetBool, Trigger

class GuiClient(Node):
    def __init__(self):
        super().__init__('gui_client')

        # Servidor de acción para recibir pasos
        self.action_server = ActionServer(
            self,
            EnviarPaso,
            'gui_action',
            self.execute_callback
        )

        # Cliente de acción para calcular trayectoria
        self.act_cli = ActionClient(self, Calcular, 'calcular_trayectoria')
        if not self.act_cli.wait_for_server(timeout_sec=5.0):
            self.get_logger().error("El servidor de acciones 'calcular_trayectoria' no está disponible.")
            rclpy.shutdown()
            return

        # Servicios
        self.cli_vis = self.create_client(Trigger,'set_modo_simulacion')
        self.cli = self.create_client(Activar, 'activar')
        self.cli1 = self.create_client(SetBool, 'finalizar_cinematica')
        self.cli_sim = self.create_client(Trigger, 'modo_simulacion')
        self.client_reset = self.create_client(Trigger, 'reiniciar_trayectoria')

        # Espera de servicios
        for cli, name in [
            (self.cli, 'activar'),
            (self.cli_sim, 'modo_simulacion'),
            (self.client_reset, 'reiniciar_trayectoria'),
            (self.cli_vis, 'set_modo_simulacion')
        ]:
            while not cli.wait_for_service(timeout_sec=1.0):
                self.get_logger().info(f"Esperando servicio '{name}'...")

        self.req = Activar.Request()

        self.configurar_modo()

    def resetear_trayectoria(self):
        req_reset = Trigger.Request()
        future = self.client_reset.call_async(req_reset)
        rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)
        if future.result():
            self.get_logger().warn(future.result().message)

    def configurar_modo(self):
        #sim_input = input("¿Activar modo simulación? (true/false): ").strip().lower()
        sim_input = "false"
        if sim_input == "true":
            req = Trigger.Request()
            future = self.cli_sim.call_async(req)
            rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)
            if future.result():
                self.get_logger().warn(future.result().message)
            
            future1 = self.cli_vis.call_async(req)
            rclpy.spin_until_future_complete(self, future1, timeout_sec=5.0)
            if future.result():
                self.get_logger().warn(future.result().message)

    def send_request(self, data):
        self.req.indicacion = data
        future = self.cli.call_async(self.req)
        rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)
        if future.result() is None:
            self.get_logger().error("Error al comunicarse con el servicio 'activar'.")
            return None
        return future.result()

    def send_req_action(self, mode):
        goal_msg = Calcular.Goal()
        goal_msg.indicacion = mode

        send_goal_future = self.act_cli.send_goal_async(goal_msg)
        rclpy.spin_until_future_complete(self, send_goal_future, timeout_sec=10.0)

        goal_handle = send_goal_future.result()
        if not goal_handle or not goal_handle.accepted:
            self.get_logger().error('Error al solicitar trayectoria.')
            return False

        self.get_logger().info('Calculando...')
        get_result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, get_result_future, timeout_sec=10.0)

        result = get_result_future.result()
        return result.result.flag if result else False

    def send_req_service(self):
        req = SetBool.Request()
        req.data = True
        future = self.cli1.call_async(req)
        rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)

    # Callback del nuevo servidor de acción (para pasos externos)
    async def execute_callback(self, goal_handle):
        paso = goal_handle.request.paso
        self.get_logger().info(f"Recibido paso desde control_node: {paso}")

        if 0 <= paso <= 4:
            self.resetear_trayectoria()
            action_response = self.send_req_action(paso)
            self.get_logger().info('Calculado' if action_response else 'Error')

            if action_response:
                self.send_request(True)
                goal_handle.succeed()
                return EnviarPaso.Result(recibido=True)
            else:
                goal_handle.abort()
                return EnviarPaso.Result(recibido=False)

        elif paso > 4:
            self.send_request(False)
            self.send_req_service()
            goal_handle.succeed()
            return EnviarPaso.Result(recibido=True)

        else:
            self.get_logger().warn("Paso inválido.")
            goal_handle.abort()
            return EnviarPaso.Result(recibido=False)

def main(args=None):
    rclpy.init(args=args)
    gui_client = GuiClient()

    if not gui_client.act_cli or not gui_client.cli:
        return

    rclpy.spin(gui_client)
    gui_client.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
