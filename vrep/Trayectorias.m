clear
rosshutdown          % cierra cualquier conexión previa

%CÁLCULO DE TRAYECTORIAS 
data          = readtable('objetos.csv');
data_ordenada = sortrows(data, 'x_m');
matriz        = table2array(data_ordenada);

idx_robot   = find(matriz(:,3) == 2);
robot_pos   = matriz(idx_robot, 1:2);
punto_dest  = matriz(3, 1:2);
codigo_dest = matriz(3, 3);

d        = 0.1;
v        = punto_dest - robot_pos;
v_unit   = v / norm(v);
p_parada = punto_dest - d*v_unit;

tray1_x = linspace(robot_pos(1), p_parada(1), 20);
tray1_y = linspace(robot_pos(2), p_parada(2), 20);

figure;
hold on; grid on; axis equal;
xlabel('x [m]');
ylabel('y [m]');


p_final = [0, 1.2];         % default
if codigo_dest == 0
    p_final = [0, 0.2]; 
end

tray2_x = linspace(punto_dest(1), p_final(1), 20);
tray2_y = linspace(punto_dest(2), p_final(2), 20);

trayectoria1 = [tray1_x', tray1_y'];
trayectoria2 = [tray2_x', tray2_y'];

% Puntos
scatter(matriz(:,1), matriz(:,2), 60, matriz(:,3), 'filled');  % puntos con color_code

% Trayectorias
plot(tray1_x , tray1_y, 'r-', 'LineWidth', 2);     % Robot → Primer punto
plot(tray2_x, tray2_y, 'g--', 'LineWidth', 2);    % Primer punto → destino final

% puntos
plot(robot_pos(1), robot_pos(2), 'ko', 'MarkerSize', 10, 'LineWidth', 2); % robot
plot(punto_dest(1), punto_dest(2), 'bx', 'MarkerSize', 10, 'LineWidth', 2); % primer punto
plot(p_final(1), p_final(2), 'ms', 'MarkerSize', 10, 'LineWidth', 2); % punto final

legend('Puntos', 'Trayectoria 1', 'Trayectoria 2', 'Robot', 'Destino intermedio', 'Destino final');
title('Trayectorias del robot');

% NODO Y PUBLICADORES
node = ros2node("/matlab_node");
pub1 = ros2publisher(node,"/trayectoria1","geometry_msgs/PoseArray");
pub2 = ros2publisher(node,"/trayectoria2","geometry_msgs/PoseArray");

% FUNCIÓN AUXILIAR PARA CREAR PoseArray
make_pose_array = @(tray) ...
    struct( ...
        'header', struct( ...
            'stamp',   struct('sec', int32(0), 'nanosec', uint32(0)), ...
            'frame_id','map'), ...
        'poses', arrayfun(@(i) struct( ...
            'position',    struct('x', tray(i,1), 'y', tray(i,2), 'z', 0.0), ...
            'orientation', struct('x', 0.0, 'y', 0.0, 'z', 0.0, 'w', 1.0)...
        ), 1:size(tray,1)) ...
    );

msg1 = make_pose_array(trayectoria1);
msg2 = make_pose_array(trayectoria2);
%  PUBLICAR
pause(1)        % da tiempo a ROS 2 a descubrir al publisher
send(pub1,msg1);
send(pub2,msg2);
disp( "Trayectorias enviadas");
