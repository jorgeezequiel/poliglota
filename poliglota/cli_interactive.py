"""Interactive guided CLI for Poliglota."""

from __future__ import annotations

from pathlib import Path

from poliglota import cli
from poliglota.formats.operations import discover_resources
from poliglota.formats.registry_init import get_registry as get_global_registry
from poliglota.translation_workflow import translate_resource_files


class InteractiveCancelled(Exception):
    pass


def _prompt_input(prompt: str, default: str | None = None) -> str:
    try:
        full_prompt = f"{prompt} [{default}]: " if default is not None else f"{prompt}: "
        value = input(full_prompt)
        if value == "":
            if default is not None:
                return default
            raise InteractiveCancelled
        return value.strip()
    except EOFError:
        raise InteractiveCancelled
    except KeyboardInterrupt:
        raise InteractiveCancelled


def _prompt_yes_no(prompt: str, default: bool = False) -> bool:
    try:
        default_str = "S/N" if default else "s/N"
        value = input(f"{prompt} ({default_str}): ").strip().lower()
        if value == "":
            return default
        if value in {"s", "sim", "y", "yes", "true", "1"}:
            return True
        if value in {"n", "nao", "não", "no", "false", "0"}:
            return False
        return default
    except EOFError:
        raise InteractiveCancelled
    except KeyboardInterrupt:
        raise InteractiveCancelled


def _prompt_choice(prompt: str, choices: list[str], default: int = 0) -> int:
    for _i, _choice in enumerate(choices):
        pass
    try:
        value = input(f"Escolha [1-{len(choices)}] (padrão {default + 1}): ").strip()
        if value == "":
            return default
        idx = int(value) - 1
        if 0 <= idx < len(choices):
            return idx
        msg = "Opção inválida"
        raise ValueError(msg)
    except EOFError:
        raise InteractiveCancelled
    except KeyboardInterrupt:
        raise InteractiveCancelled


def run_interactive() -> int:

    try:
        devices = ["auto", "cpu", "cuda", "mps"]
        dev_idx = _prompt_choice("Selecione o dispositivo:", devices, default=0)
        device = devices[dev_idx]
        try:
            resolved = cli._resolve_device_name(device)
            if device not in ("auto", resolved):
                pass
            if device != "auto" and resolved == "cpu" and device in ["cuda", "mps"]:
                return 1
        except Exception:
            return 1

        registry = get_global_registry()
        formats = registry.names()
        fmt_idx = _prompt_choice(
            "Selecione o formato:", formats, default=formats.index("arb") if "arb" in formats else 0
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

        target_locales = []
        for loc in locales_list:
            if loc == source_locale:
                continue
            if _prompt_yes_no(f"Traduzir para {loc}?", default=False):
                target_locales.append(loc)
        if not target_locales:
            return 1

        try:
            default_model = cli._select_default_motor(source_locale, target_locales[0])
            use_default = _prompt_yes_no("Usar modelo padrão sugerido?", default=True)
            if use_default:
                model = default_model
            else:
                model_str = _prompt_input("Nome do modelo (HuggingFace)")
                model = model_str or default_model
        except Exception:
            return 1

        out_str = _prompt_input(
            "Diretório para arquivos traduzidos (separado dos originais)",
            default=str(root / ".poliglota_translated"),
        )
        output_dir = Path(out_str)

        if not _prompt_yes_no("Iniciar tradução?", default=False):
            return 0

        try:
            report = translate_resource_files(
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
            if report.failed > 0 and report.details:
                for _d in report.details[:10]:
                    pass
                if len(report.details) > 10:
                    pass
            return 0
        except Exception:
            return 1

    except InteractiveCancelled:
        return 0
    except Exception:
        return 1
