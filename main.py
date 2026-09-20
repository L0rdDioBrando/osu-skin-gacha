"""Shared entry point for source, installed package and frozen builds."""
def main():
    from modules.skin_gacha import main as run
    return run()

if __name__ == "__main__":
    main()
