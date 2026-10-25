# EDA Technology

`kotoba.technology/:eda` is the stable business-facing handle for electronic
design automation.

Business blueprints should depend on the capability contract:

- `:design/electronics`
- `:verification/formal`
- `:simulation/circuit`
- `:manufacturing/pcb`

They should not depend directly on one EDA implementation.
