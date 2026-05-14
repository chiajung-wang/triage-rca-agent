import argparse


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="triage-rca",
        description="Bug triage and RCA for Python codebases"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Triage a bug report and optionally run RCA")
    run_p.add_argument("--issue", required=True, help="Bug report text")
    run_p.add_argument("--repo", required=True, help="Path to target Python repo")
    run_p.add_argument("--interactive", action="store_true",
                       help="Pause for human input when stuck")

    eval_p = sub.add_parser("eval", help="Run eval harness")
    eval_p.add_argument("mode", choices=["rca", "triage"], help="Eval mode")

    args = parser.parse_args()

    if args.command == "run":
        from triage_rca.orchestrator import run_pipeline
        run_pipeline(issue=args.issue, repo_path=args.repo, interactive=args.interactive)
    elif args.command == "eval":
        from triage_rca.eval import run_eval
        run_eval(mode=args.mode)
