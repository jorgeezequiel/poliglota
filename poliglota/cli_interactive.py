"""Interactive guided CLI for Poliglota."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from poliglota import cli, gpu
from poliglota.formats.operations import discover_resources
from poliglota.formats.registry_init import get_registry as get_global_registry
from poliglota.language_detection import detect_source_locale, normalize_locale_code
from poliglota.translation_workflow import translate_resource_files

_console = Console(stderr=False, force_terminal=True)


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
    """Prompt the user for a yes/no value with a negative default."""
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

        print(f"Entrada inválida. Use s/Sim ou n/Não. [{default_str}]")


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
            print(f"Entrada inválida. Digite um número entre 1 e {len(choices)}.")
            continue

        if 1 <= selected <= len(choices):
            return selected - 1

        print(f"Opção fora do intervalo. Digite um número entre 1 e {len(choices)}.")


def run_interactive() -> int:
    """Run the guided CLI flow for validating and translating locale resources."""
    try:
        devices = ["auto", "cpu", "cuda", "mps"]
        dev_idx = _prompt_choice("Selecione o dispositivo:", devices, default=0)
        device = devices[dev_idx]
        resolved = cli.resolve_device_name(device)
        if device != "auto" and resolved == "cpu" and device in {"cuda", "mps"}:
            raise ValueError(
                f"O dispositivo '{device}' não está disponível neste ambiente. "
                "Use CPU ou escolha outra opção."
            )

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
            raise ValueError(f"O caminho '{root}' não existe. Verifique a pasta informada.")
        if root.is_file():
            raise ValueError(
                f"O caminho '{root}' aponta para um arquivo, mas a operação espera uma pasta "
                "com recursos de localização."
            )

        adapter = registry.get(format_name)
        by_locale = discover_resources(adapter, root)
        if not by_locale:
            if any(root.rglob(f"*.{format_name}")):
                raise ValueError(
                    f"Nenhum locale foi reconhecido em '{root}' para o formato '{format_name}'. "
                    "Verifique a estrutura esperada ou a análise de conteúdo."
                )
            raise ValueError(
                f"Nenhum arquivo '{format_name}' foi encontrado em '{root}'. "
                f"Verifique o caminho informado e o formato selecionado ({format_name})."
            )

        detection = detect_source_locale(root, format_name, adapter=adapter)
        if detection.inconclusive:
            print("A detecção de idioma foi inconclusiva. O próximo passo exige confirmação manual.")

        locale_candidates = [
            normalize_locale_code(candidate.locale_code) or candidate.locale_code
            for candidate in detection.candidates
        ]
        if locale_candidates:
            locales_list = sorted(set(by_locale.keys()) | set(locale_candidates))
        else:
            locales_list = sorted(by_locale.keys())
        if not locales_list:
            raise ValueError("Nenhum idioma foi encontrado para esta pasta.")
        src_idx = _prompt_choice("Selecione o idioma de origem:", locales_list, default=0)
        source_locale = locales_list[src_idx]

        target_locales: list[str] = []
        for loc in locales_list:
            if loc == source_locale:
                continue
            if _prompt_yes_no(f"Traduzir para {loc}?"):
                target_locales.append(loc)
        if not target_locales:
            raise ValueError(
                "Nenhum idioma de destino selecionado. É necessário escolher pelo menos um destino."
            )

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

        is_cached = gpu.check_model_cached(model)
        if not is_cached:
            if not _prompt_yes_no(f"Baixar e preparar o modelo {model}?", default=False):
                print("Preparação cancelada. Nenhum modelo foi baixado.")
                return 0
            try:
                cli._prepare_model_locally(model, resolved)
            except RuntimeError as exc:
                print(f"Erro: {exc}")
                return 1

        if not _prompt_yes_no("Iniciar tradução?", default=False):
            print("Tradução cancelada pelo usuário.")
            return 0

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
        processed = getattr(report, "processed", 0)
        translated = getattr(report, "translated", 0)
        skipped = getattr(report, "skipped", 0)
        failed = getattr(report, "failed", 0)
        details = getattr(report, "details", []) or []
        if not isinstance(processed, int):
            processed = 0
        if not isinstance(translated, int):
            translated = 0
        if not isinstance(skipped, int):
            skipped = 0
        if not isinstance(failed, int):
            failed = 0
        if not isinstance(details, list):
            details = []
        print("Resumo da execução:")
        print(f"  Idiomas encontrados: {', '.join(locales_list)}")
        print(f"  Origem: {source_locale}")
        print(f"  Destinos: {', '.join(target_locales)}")
        print(f"  Arquivos processados: {processed}")
        print(f"  Traduções realizadas: {translated}")
        print(f"  Itens ignorados: {skipped}")
        print(f"  Falhas: {failed}")
        if details and failed > 0:
            print("  Detalhes de falha:")
            for detail in details[:10]:
                print(
                    f"    - {detail.get('file', 'arquivo desconhecido')}: "
                    f"{detail.get('error', 'erro desconhecido')}"
                )
        print(f"Arquivos gerados em: {output_dir}")
    except InteractiveCancelledError:
        print("Operação cancelada pelo usuário.")
        return 0
    except (RuntimeError, ValueError, OSError, TypeError) as exc:
        print(f"Erro: {exc}")
        return 1
    else:
        return 0
