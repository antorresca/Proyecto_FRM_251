import rclpy
from rclpy.node import Node
from std_srvs.srv import Trigger
from std_msgs.msg import Int32
import RPi.GPIO as GPIO
import time

class GripperNode(Node):
    def __init__(self):
        super().__init__('gripper_node')

        # Estado del gripper: 0 = cerrado, 1 = abierto
        self.estado = 0

        # Pin GPIO (usa numeración BCM)
        self.pin_gripper = 18  # GPIO18

        # Configuración inicial del GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pin_gripper, GPIO.OUT)

        # Servicio ROS 2
        self.srv = self.create_service(Trigger, 'activar_gripper', self.callback_trigger)

        # Publicador del estado
        self.publisher = self.create_publisher(Int32, '/gripper_estado', 10)

        self.get_logger().info('Nodo de gripper listo (PWM solo se activa temporalmente)')

    def callback_trigger(self, request, response):
        # Alternar estado
        if self.estado == 0:
            self.estado = 1
            self.abrir()
        else:
            self.estado = 0
            self.cerrar()

        # Publicar estado
        msg = Int32()
        msg.data = self.estado
        self.publisher.publish(msg)

        response.success = True
        response.message = f'Gripper {"abierto" if self.estado == 1 else "cerrado"}'
        return response

    def set_angle(self, angle):
        """Aplica el ángulo deseado momentáneamente para evitar sobrecalentar el servo"""
        pwm = GPIO.PWM(self.pin_gripper, 50)  # 50 Hz
        pwm.start(0)

        duty = 2 + (angle / 18)
        pwm.ChangeDutyCycle(duty)
        self.get_logger().info(f'Duty cycle aplicado: {duty:.2f}')

        # Esperar para permitir el movimiento del servo
        time.sleep(0.5)

        pwm.ChangeDutyCycle(0)  # Detener movimiento
        pwm.stop()  # Desactivar PWM completamente

    def abrir(self):
        self.get_logger().info('>> Abriendo gripper...')
        self.set_angle(90)

    def cerrar(self):
        self.get_logger().info('>> Cerrando gripper...')
        self.set_angle(0)

    def destroy_node(self):
        self.get_logger().info('Liberando recursos GPIO...')
        GPIO.cleanup()
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    node = GripperNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
