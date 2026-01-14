import asyncio
import traceback
import inspect

from openagents.core.network import NetworkConfig, create_topology


async def create_basic_topology():
    print("👉 1. 构造 NetworkConfig")

    config = NetworkConfig(
        name="ProgrammaticNetwork",
        mode="centralized",          # 会在内部转成 NetworkMode
        node_id="python-network-1",
        transports=[
            {
                "type": "http",
                "config": {
                    "port": 8700,
                    "host": "127.0.0.1",   # 先只对本机开放
                },
            },
            {
                "type": "grpc",
                "config": {
                    "port": 8600,
                    "max_message_size": 52428800,
                    "compression": "gzip",
                },
            },
        ],
        # 先不加载 mods，确认网络本体能起来，后面再一点点加回
        mods=[],
    )

    print("✅ 2. NetworkConfig OK，调用 create_topology")

    # 函数签名：(mode, node_id, config) -> NetworkTopology
    topology = create_topology(config.mode, config.node_id, config)
    print("✅ 3. 得到 NetworkTopology =", type(topology))

    # ⭐ 关键：直接启动拓扑（它内部会管理 network/server 等）
    if hasattr(topology, "start"):
        print("ℹ️ 4. 启动 topology")
        if inspect.iscoroutinefunction(topology.start):
            await topology.start()
        else:
            topology.start()
        print("✅ 5. topology.start 完成，应已在监听端口")
    else:
        print("⚠️ topology 上没有 start 方法，无法启动服务")

    print("🎉 拓扑启动逻辑执行完毕")
    print("🌐 HTTP 访问地址：  http://127.0.0.1:8700")
    print("🔌 gRPC 访问地址： localhost:8600")

    return topology


async def main():
    topology = None

    try:
        print("==== 程序开始运行 ====")
        topology = await create_basic_topology()
        print("==== 进入等待阶段 ====")

        # 优雅等待退出：优先用 topology.wait_for_shutdown
        if hasattr(topology, "wait_for_shutdown"):
            print("⌛ 调用 topology.wait_for_shutdown（Ctrl+C 可中断）")
            if inspect.iscoroutinefunction(topology.wait_for_shutdown):
                await topology.wait_for_shutdown()
            else:
                topology.wait_for_shutdown()
        else:
            print("⌛ 没有 wait_for_shutdown，用 sleep 挂起（Ctrl+C 退出）")
            while True:
                await asyncio.sleep(3600)

    except Exception as e:
        print("❌ 发生异常：", repr(e))
        traceback.print_exc()

    finally:
        print("🛑 main() 结束，准备退出程序")
        if topology is not None and hasattr(topology, "stop"):
            print("🧹 尝试停止 topology")
            try:
                if inspect.iscoroutinefunction(topology.stop):
                    await topology.stop()
                else:
                    topology.stop()
            except Exception as e:
                print("停止 topology 时出错：", repr(e))


if __name__ == "__main__":
    asyncio.run(main())
