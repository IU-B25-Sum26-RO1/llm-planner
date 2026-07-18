import os

import rclpy # type: ignore
from rclpy.node import Node # type: ignore
from rclpy.action import ActionServer, CancelResponse, GoalResponse # type: ignore

from robot_interfaces.action import BaseAction # type: ignore
from robot_interfaces.srv import GripperControl # type: ignore

class UR10eInterface(Node):
    def __init__(self):
        super().__init__('ur10e_interface')

        base_action_topic = '/execute/base_action'
        gripper_control_topic = '/execute/gripper_control'

        self._action_server = ActionServer(
            self,
            BaseAction,
            base_action_topic,
            execute_callback=self.execute_callback,
            goal_callback=self.goal_callback,
            cancel_callback=self.cancel_callback 
        )

        self.gripper_srv = self.create_service(
            GripperControl, gripper_control_topic, self.gripper_callback
        )

        self.get_logger().info('UR10e Interface | Robot Interface has launched')
    
    def goal_callback(self):
        pass

    def cancel_callback(self, cancel_request):
        # Тут мы тупо принимаем запрос на отмену
        self.get_logger().warn('UR10e Interface | Got emergency cancel command.')
        return CancelResponse.ACCEPT

    def execute_callback(self, goal_handle):
        """
        Executes received action
        Parameters:
            goal_handle:
                goal_handle.request - .action объект. Поля описаны в ./src/robot_interfaces/action/BaseAction.action
                    request.task_type - тип задачи (пока что pick/place/move_to, потом как нех делать расширим)
                    request.object_name - имя объекта (для поиска кордов, для pick/place)
                    [request.x, request.y, request.z] корды (опционально, для move_to)
        """
        request = goal_handle.request
        task = request.task_type # string: pick | place | move_to

        # TODO: также реализовать проверку на возможную отмену 
        if goal_handle.is_cancel_requested:
            # Остановка робота

            goal_handle.canceled()
            self.is_busy = False

            self.get_logger().info("UR10e Interface | Robot stopped.")
            result = BaseAction.Result()
            result.success = False
            return result 

        if task == "pick":
            self._pick(...)
        elif task == "place":
            self._place(...)
        elif task == "move_to":
            self._move_to(...)
        else:
            self.get_logger().warn(f"UR10e Interface | Unexpected task: {task}")
    
    def gripper_callback(self, request, response):
        try:
            if request.activate:
                # TODO: логика закрывания гриппера 
                self.get_logger().info("UR10e Interface | Gripper closed")
            else:
                # TODO: логика открывания гриппера 
                self.get_logger().info("UR10e Interface | Gripper opened")
            
        except Exception as e:
            self.get_logger().error(f"UR10e Interface | Unexpected gripper error: {str(e)}")
            response.success = False
            return response
        
        response.success = True
        return response 
    
    def _pick(self, *args):
        pass
        # TODO: реализация pick: вытащить корды, подвести гриппер схватить (, вернуться обратно?).

    def _place(self, *args):
        pass
        # TODO: реализация place: вытащить корды места назначения, подвести, положить, вернуться

    def _move_to(self, *args):
        pass
        # TODO: реализация move_to: просто подвести гриппер на (x, y, z)