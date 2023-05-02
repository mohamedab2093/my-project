#!/bin/bash

set -e

# set the postgres database host, port, user and password according to the environment
# and pass them as arguments to the odoo process if not present in the config file
: ${HOST:=${DB_PORT_5432_TCP_ADDR:='db'}}
: ${PORT:=${DB_PORT_5432_TCP_PORT:=5432}}
: ${USER:=${DB_ENV_POSTGRES_USER:=${POSTGRES_USER:='odoo'}}}
: ${PASSWORD:=${DB_ENV_POSTGRES_PASSWORD:=${POSTGRES_PASSWORD:='odoo'}}}

DB_ARGS=()
function check_db_config() {
    param="$1"
    value="$2"
    if grep -q -E "^\s*\b${param}\b\s*=" "$ODOO_RC" ; then
        value=$(grep -E "^\s*\b${param}\b\s*=" "$ODOO_RC" |cut -d " " -f3|sed 's/["\n\r]//g')
    fi;

    DB_ARGS+=("--${param}")
    DB_ARGS+=("${value}")
}
check_db_config "db_host" "$HOST"
check_db_config "db_port" "$PORT"
check_db_config "db_user" "$USER"
check_db_config "db_password" "$PASSWORD"


# : ${REDIS_ENABLED:='True'}
# : ${REDIS_HOST:='localhost'}
# : ${REDIS_PORT:=6379}
# : ${REDIS_DBINDEX:=1}
# : ${REDIS_PASS:='None'}


function update_redis_config() {
    param="$1"
    value="$2"
    $(sed -i -r s/";? ?${param} ?= ?.*"/"${param} = ${value}"/g "$ODOO_RC")
}

# update_redis_config "enable_redis" "$REDIS_ENABLED"
# update_redis_config "enable_redis" "True"
# update_redis_config "redis_host" "$REDIS_HOST"
# update_redis_config "redis_port" "$REDIS_PORT"
# update_redis_config "redis_dbindex" "$REDIS_DBINDEX"
update_redis_config "redis_pass" "$REDIS_PASS"

case "$1" in
    -- | odoo)
        shift
        if [[ "$1" == "scaffold" ]] ; then
            exec odoo "$@"
        else
            exec odoo "$@" "${DB_ARGS[@]}"
        fi
        ;;
    -*)
        exec odoo "$@" "${DB_ARGS[@]}"
        ;;
    *)
        exec "$@"
esac

exit 1