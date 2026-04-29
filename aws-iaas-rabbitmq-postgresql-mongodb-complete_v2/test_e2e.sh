#!/bin/bash
set -e

LB="52.91.13.99"

echo "=== POST /orders ==="
RESP=$(curl -s -X POST http://$LB/orders \
  -H "Content-Type: application/json" \
  -d '{"description":"e2e-test"}')
echo "$RESP"
TASK_ID=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('task_id',''))")
ORDER_ID=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('order_id',''))")
echo "task_id=$TASK_ID  order_id=$ORDER_ID"

if [ -z "$TASK_ID" ]; then
  echo "ERROR: no task_id in response"
  exit 1
fi

echo ""
echo "=== Waiting 8s for worker_post to process ==="
sleep 8

echo "=== GET /tasks/$TASK_ID ==="
TASK=$(curl -s http://$LB/tasks/$TASK_ID)
echo "$TASK"

echo ""
echo "=== GET /orders (find latest order) ==="
ORDERS=$(curl -s http://$LB/orders)
echo "$ORDERS" | python3 -c "import sys,json; orders=json.load(sys.stdin); print('Orders count:', len(orders))"
ORDER_ID=$(echo "$ORDERS" | python3 -c "import sys,json; orders=json.load(sys.stdin); print(orders[-1]['order_id']) if orders else print('')")
echo "Latest order_id=$ORDER_ID"

echo ""
echo "=== DELETE /orders/$ORDER_ID ==="
DEL=$(curl -s -X DELETE http://$LB/orders/$ORDER_ID)
echo "$DEL"
DEL_TASK=$(echo "$DEL" | python3 -c "import sys,json; print(json.load(sys.stdin).get('task_id',''))")
echo "delete task_id=$DEL_TASK"

echo ""
echo "=== Waiting 8s for worker_delete to process ==="
sleep 8

echo "=== GET /tasks/$DEL_TASK ==="
curl -s http://$LB/tasks/$DEL_TASK
echo ""
echo "TEST_COMPLETE"
