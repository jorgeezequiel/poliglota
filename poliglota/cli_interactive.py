"""Interactive guided CLI for Poliglota."""

from __future__ import annotations

from pathlib import Path

from poliglota import cli
from poliglota.formats.operations import discover_resources
from poliglota.formats.registry_init import get_registry as get_global_registry
from poliglota.translation_workflow import translate_resource_files


class InteractiveCancelledError(Exception):
    """Raised when the interactive flow is interrupted by the user."""


def _prompt_input(prompt: str, default: str | None = None) -> str:
    """Prompt the user for a value, returning the default if it is blank."""
    try:
        full_prompt = f"{prompt} [{default}]: " if default is not None else f"{prompt}: "
        value = input(full_prompt)
        if value == "":
            if default is not None:
                return default
            msg = "Input is required."
            raise InteractiveCancelledError(msg)
        return value.strip()
    except EOFError as exc:
        raise InteractiveCancelledError from exc
    except KeyboardInterrupt as exc:
        raise InteractiveCancelledError from exc


def _prompt_yes_no(prompt: str, default: bool = False) -> bool:
    """Prompt the user for a yes/no value."""
    default_str = "S/N" if default else "s/N"
    true_values = {"s", "sim", "y", "yes", "true", "1"}
    false_values = {"n", "nao", "no", "false", "0"}

    while True:
        try:
            value = input(f"{prompt} ({default_str}): ").strip().lower()
        except (EOFError, KeyboardInterrupt) as exc:
            raise InteractiveCancelledError from exc

        if value == "":
            return default
        if value in true_values:
            return True
        if value in false_values:
            return False

        invalid_prompt = f"{prompt} ({default_str}) [s/n]: "
        try:
            value = input(invalid_prompt).strip().lower()
        except (EOFError, KeyboardInterrupt) as exc:
            raise InteractiveCancelledError from exc

        if value in true_values:
            return True
        if value in false_values:
            return False
        return default


def _prompt_choice(prompt: str, choices: list[str], default: int = 0) -> int:
    """Prompt the user to select one option from a list."""
    if not choices:
        msg = "No choices available for prompt."
        raise ValueError(msg)

    default_index = max(0, min(default, len(choices) - 1))
    while True:
        try:
            choices_text = "\n".join(
                f"  {idx}. {choice}{' (padrão)' if idx - 1 == default_index else ''}"
                for idx, choice in enumerate(choices, start=1)
            )
            prompt_text = (
                f"{prompt}\n{choices_text}\n"
                f"Escolha [1-{len(choices)}] (padrão {default_index + 1}): "
            )
            raw_value = input(prompt_text).strip()
        except (EOFError, KeyboardInterrupt) as exc:
            raise InteractiveCancelledError from exc

        if raw_value == "":
            return default_index

        try:
            selected = int(raw_value)
        except ValueError:
            return default_index

        if 1 <= selected <= len(choices):
            return selected - 1

        retry_prompt = (
            f"{prompt}\n{choices_text}\n"
            f"Escolha [1-{len(choices)}] (opção inválida, padrão {default_index + 1}): "
        )
        try:
            value = input(retry_prompt).strip()
        except (EOFError, KeyboardInterrupt) as exc:
            raise InteractiveCancelledError from exc

        if value == "":
            return default_index

        try:
            selected = int(value)
        except ValueError:
            return default_index

        if 1 <= selected <= len(choices):
            return selected - 1
        return default_index


def run_interactive() -> int:
    """Run the guided CLI flow for validating and translating locale resources."""
    try:
        devices = ["auto", "cpu", "cuda", "mps"]
        dev_idx = _prompt_choice("Selecione o dispositivo:", devices, default=0)
        device = devices[dev_idx]
        resolved = cli.resolve_device_name(device)
        if device != "auto" and resolved == "cpu" and device in {"cuda", "mps"}:
            return 1

        registry = get_global_registry()
        formats = registry.names()
        fmt_idx = _prompt_choice(
            "Selecione o formato:",
            formats,
            default=formats.index("arb") if "arb" in formats else 0,
        )
        format_name = formats[fmt_idx]

        root_str = _prompt_input("Caminho da pasta com arquivos de localização", default=".")
        root = Path(root_str)
        if not root.exists():
            return 1

        adapter = registry.get(format_name)
        by_locale = discover_resources(adapter, root)
        if not by_locale:
            return 1

        locales_list = sorted(by_locale.keys())
        src_idx = _prompt_choice("Selecione o idioma de origem:", locales_list, default=0)
        source_locale = locales_list[src_idx]

        target_locales: list[str] = []
        for loc in locales_list:
            if loc == source_locale:
                continue
            if _prompt_yes_no(f"Traduzir para {loc}?"):
                target_locales.append(loc)
        if not target_locales:
            return 1

        default_model = cli.select_default_motor(source_locale, target_locales[0])
        use_default = _prompt_yes_no("Usar modelo padrão sugerido?", default=True)
        if use_default:
            model = default_model
        else:
            model_str = _prompt_input("Nome do modelo (HuggingFace)", default=default_model)
            model = model_str or default_model

        out_str = _prompt_input(
            "Diretório para arquivos traduzidos (separado dos originais)",
            default=str(root / ".poliglota_translated"),
        )
        output_dir = Path(out_str)

        if not _prompt_yes_no("Iniciar tradução?", default=False):
            return 0

        translate_resource_files(
            root=root,
            source_locale=source_locale,
            target_locales=target_locales,
            format_name=format_name,
            output_dir=output_dir,
            model=model,
            device=resolved,
            batch_size=8,
            preserve_placeholders=True,
        )
    except InteractiveCancelledError:
        return 0
    except (RuntimeError, ValueError, OSError, TypeError):
        return 1
    else:
        return 0
