from agent.runtime import GODFLEXRuntime


def main():
    print("Starting GODFLEX runtime test...")

    runtime = GODFLEXRuntime()

    status = runtime.status()

    print("\nSystem status:")
    for key, value in status.items():
        print(f"{key}: {value}")

    memory = runtime.remember(
        category="test",
        content="GODFLEX runtime memory test.",
    )

    print("\nMemory test:")
    print(memory)

    results = runtime.recall("runtime memory test")

    print("\nRecall test:")
    print(results)

    print("\nRuntime test completed.")


if __name__ == "__main__":
    main()
