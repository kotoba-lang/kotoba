PROGRAM Motor
VAR_INPUT
  Enable : BOOL;
  Sensor : DINT;
END_VAR
VAR_OUTPUT
  MotorOn : BOOL;
  Command : DINT;
END_VAR

Command := Sensor + 1;
MotorOn := Enable AND Command < 100;
END_PROGRAM
