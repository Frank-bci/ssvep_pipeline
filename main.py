from argparse import ArgumentParser

from acquisition.simulator import EEGSimulator
from config import PipelineConfig
from realtime.pipeline import RealtimePipeline
from ui.dashboard import main as run_speller_ui


if __name__ == '__main__':
    parser = ArgumentParser(description="Run realtime SSVEP pipeline with simulated EEG.")
    parser.add_argument("--ui", action="store_true", help="Launch the realtime SSVEP speller UI.")
    parser.add_argument("--target", type=float, default=10.0, help="Simulated SSVEP target frequency.")
    parser.add_argument("--iterations", type=int, default=None, help="Stop after N realtime steps.")
    parser.add_argument("--seed", type=int, default=42, help="Simulator random seed.")
    args = parser.parse_args()

    if args.ui:
        run_speller_ui()
        raise SystemExit(0)

    config = PipelineConfig()
    source = EEGSimulator(
        fs=config.fs,
        channels=config.channels,
        target_freq=args.target,
        seed=args.seed,
    )
    pipeline = RealtimePipeline(config=config, source=source)

    pipeline.run(max_iterations=args.iterations)
