from __future__ import annotations
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime


# ===========================================================================
# EXCEÇÕES DE REGRAS DE NEGÓCIO
# ===========================================================================
class RegraNegocioError(Exception):
    """Exceção base para violações de regras de negócio."""


class QuantidadeMinimaError(RegraNegocioError):
    """Quantidade inferior ao mínimo permitido (25 kg)."""


class EstoqueInsuficienteError(RegraNegocioError):
    """Quantidade solicitada maior que a disponível."""


# ===========================================================================
# ENUMS
# ===========================================================================
class CategoriaProduto(Enum):
    FRESCO = "fresco"
    CONGELADO = "congelado"


class StatusPedido(Enum):
    CRIADO = "criado"
    RECEBIDO = "recebido"
    ACEITO = "aceito"
    REJEITADO = "rejeitado"
    AJUSTE_SOLICITADO = "ajuste_solicitado"
    EM_PREPARACAO = "em_preparacao"
    EM_ENTREGA = "em_entrega"
    ENTREGUE = "entregue"


class StatusEmpresa(Enum):
    DISPONIVEL = "verde"
    ESTOQUE_BAIXO = "laranja"
    FORA_DO_HORARIO = "vermelho"


# ===========================================================================
# EMPRESA (classe base)
# ===========================================================================
class Empresa:
    """
    Representa uma empresa do projeto Marisqueiras da Ilha.
    RN01: modelo B2B (somente empresas).
    RN02: 1 habitação = 1 empresa.
    P12: uma pessoa por habitação responde pelo cadastro/acesso.
    P33: indicador visual (verde/laranja/vermelho).
    """

    def __init__(
        self,
        nome: str,
        localizacao: str,
        responsavel: str,
        horario_funcionamento: Tuple[int, int],  # (hora_abertura, hora_fechamento)
    ):
        if not nome or not isinstance(nome, str):
            raise ValueError("Nome da empresa é obrigatório.")
        if not localizacao:
            raise ValueError("Localização é obrigatória.")
        if not responsavel:
            raise ValueError("Uma pessoa por habitação deve ser responsável. P12")
        if (
            not isinstance(horario_funcionamento, tuple)
            or len(horario_funcionamento) != 2
            or horario_funcionamento[0] >= horario_funcionamento[1]
        ):
            raise ValueError("Horário deve ser uma tupla (abertura, fechamento).")

        self.nome = nome
        self.localizacao = localizacao
        self.responsavel = responsavel
        self.horario_funcionamento = horario_funcionamento

    def esta_no_horario(self, hora_atual: Optional[int] = None) -> bool:
        """Verifica se a empresa está dentro do horário de funcionamento."""
        if hora_atual is None:
            hora_atual = datetime.now().hour
        abertura, fechamento = self.horario_funcionamento
        return abertura <= hora_atual < fechamento

    def __str__(self) -> str:
        return f"{self.nome} ({self.localizacao})"


# ===========================================================================
# EMPRESA MARISQUEIRA
# ===========================================================================
class EmpresaMarisqueira(Empresa):
    """
    Empresa fornecedora (marisqueira).
    RN03: pode atuar individualmente.
    RN12: visualiza apenas os próprios produtos.
    RN22: realiza a entrega e atualiza o status.
    P33: permanece cadastrada mesmo sem estoque.
    """

    def __init__(
        self,
        nome: str,
        localizacao: str,
        responsavel: str,
        horario_funcionamento: Tuple[int, int],
    ):
        super().__init__(nome, localizacao, responsavel, horario_funcionamento)
        self.produtos: List["Produto"] = []
        self.pedidos_recebidos: List["Pedido"] = []
        self.avaliacoes_recebidas: List["Avaliacao"] = []

    # -----------------------------------------------------------------------
    # Cadastro de produtos
    # -----------------------------------------------------------------------
    def cadastrar_produto(
        self,
        nome: str,
        categoria: CategoriaProduto,
        preco: float,
        quantidade_disponivel: int,
        foto: Optional[str] = None,
    ) -> "Produto":
        """
        Cadastra um produto. RN06, P15, P16, P18.
        Fresco e congelado são produtos distintos (mesmo nome, categorias diferentes).
        """
        for p in self.produtos:
            if p.nome.lower() == nome.lower() and p.categoria == categoria:
                raise RegraNegocioError(
                    f"Já existe um produto '{nome}' na categoria {categoria.value}. RN06"
                )
        novo = Produto(nome, categoria, preco, quantidade_disponivel, self, foto)
        self.produtos.append(novo)
        return novo

    def consultar_proprios_produtos(self) -> List["Produto"]:
        """RN12 / P25: a marisqueira vê apenas os próprios produtos."""
        return list(self.produtos)

    # -----------------------------------------------------------------------
    # Ciclo de vida do pedido
    # -----------------------------------------------------------------------
    def receber_pedido(self, pedido: "Pedido") -> None:
        """Recebe um pedido. RN07."""
        self._validar_pedido(pedido)
        pedido.receber_pedido()
        self.pedidos_recebidos.append(pedido)

    def aceitar_pedido(self, pedido: "Pedido") -> None:
        """Aceita o pedido e dá baixa no estoque. RN07, RN08, RN18."""
        self._validar_pedido(pedido)
        pedido.aceitar_pedido()

    def rejeitar_pedido(self, pedido: "Pedido", motivo: str = "") -> None:
        """Rejeita o pedido. RN07."""
        self._validar_pedido(pedido)
        pedido.rejeitar_pedido(motivo)

    def solicitar_ajuste(self, pedido: "Pedido", mensagem: str) -> None:
        """Solicita ajuste ao comprador. RN07."""
        self._validar_pedido(pedido)
        pedido.solicitar_ajuste(mensagem)

    def atualizar_status_entrega(
        self, pedido: "Pedido", novo_status: StatusPedido
    ) -> None:
        """Atualiza o status da entrega. RN22."""
        self._validar_pedido(pedido)
        pedido.atualizar_status_entrega(novo_status)

    # -----------------------------------------------------------------------
    # Avaliações
    # -----------------------------------------------------------------------
    def registrar_avaliacao(self, avaliacao: "Avaliacao") -> None:
        """Registra uma avaliação recebida. RN21."""
        if avaliacao.empresa_marisqueira is not self:
            raise RegraNegocioError("Avaliação não pertence a esta empresa.")
        self.avaliacoes_recebidas.append(avaliacao)

    def media_avaliacoes(self) -> float:
        """Média das avaliações recebidas (0.0 se não houver)."""
        if not self.avaliacoes_recebidas:
            return 0.0
        return sum(a.nota for a in self.avaliacoes_recebidas) / len(
            self.avaliacoes_recebidas
        )

    # -----------------------------------------------------------------------
    # Indicador visual
    # -----------------------------------------------------------------------
    def status_visual(self, hora_atual: Optional[int] = None) -> StatusEmpresa:
        """
        Retorna o status visual da empresa. P33 / RN20.
        - vermelho: fora do horário de funcionamento
        - laranja: dentro do horário, mas sem produto com estoque >= 25 kg
        - verde: dentro do horário e com pelo menos um produto disponível
        """
        if not self.esta_no_horario(hora_atual):
            return StatusEmpresa.FORA_DO_HORARIO
        if any(p.quantidade_disponivel >= 25 for p in self.produtos):
            return StatusEmpresa.DISPONIVEL
        return StatusEmpresa.ESTOQUE_BAIXO

    # -----------------------------------------------------------------------
    # Auxiliares
    # -----------------------------------------------------------------------
    def _validar_pedido(self, pedido: "Pedido") -> None:
        if not isinstance(pedido, Pedido):
            raise ValueError("Pedido inválido.")
        if pedido.empresa_marisqueira is not self:
            raise RegraNegocioError("Pedido não pertence a esta empresa.")


# ===========================================================================
# EMPRESA COMPRADORA
# ===========================================================================
class EmpresaCompradora(Empresa):
    """
    Empresa que consulta produtos, realiza pedidos e avalia marisqueiras.
    RN10, RN11, RN12, RN13, RN21, RN22.
    """

    def __init__(
        self,
        nome: str,
        localizacao: str,
        responsavel: str,
        horario_funcionamento: Tuple[int, int],
    ):
        super().__init__(nome, localizacao, responsavel, horario_funcionamento)
        self.pedidos_realizados: List["Pedido"] = []
        self.avaliacoes_feitas: List["Avaliacao"] = []

    # -----------------------------------------------------------------------
    # Consulta e comparação
    # -----------------------------------------------------------------------
    def consultar_produtos(
        self,
        produtos_disponiveis: List["Produto"],
        nome: Optional[str] = None,
        categoria: Optional[CategoriaProduto] = None,
        localizacao: Optional[str] = None,
        empresa_marisqueira: Optional[EmpresaMarisqueira] = None,
        avaliacao_minima: Optional[float] = None,
        ordenar_por: Optional[str] = None,
    ) -> List["Produto"]:
        """
        Consulta produtos com filtros e ordenação. RN10, RN11 / P9, P21, P22.
        Filtros: nome, categoria, localização, empresa/marisqueira, avaliação.
        Ordenação: 'menor_preco', 'maior_preco', 'melhor_avaliacao', 'localizacao'.
        """
        resultado: List["Produto"] = []
        for p in produtos_disponiveis:
            if nome and nome.lower() not in p.nome.lower():
                continue
            if categoria and p.categoria != categoria:
                continue
            if localizacao and p.empresa.localizacao != localizacao:
                continue
            if empresa_marisqueira and p.empresa is not empresa_marisqueira:
                continue
            if (
                avaliacao_minima is not None
                and p.empresa.media_avaliacoes() < avaliacao_minima
            ):
                continue
            resultado.append(p)

        if ordenar_por == "menor_preco":
            resultado.sort(key=lambda p: p.preco)
        elif ordenar_por == "maior_preco":
            resultado.sort(key=lambda p: p.preco, reverse=True)
        elif ordenar_por == "melhor_avaliacao":
            resultado.sort(key=lambda p: p.empresa.media_avaliacoes(), reverse=True)
        elif ordenar_por == "localizacao":
            resultado.sort(key=lambda p: p.empresa.localizacao)
        elif ordenar_por is not None:
            raise ValueError(
                "Ordenação inválida. Use: menor_preco, maior_preco, "
                "melhor_avaliacao ou localizacao."
            )

        return resultado

    def comparar_produtos(
        self, produto_a: "Produto", produto_b: "Produto"
    ) -> Dict[str, Any]:
        """
        Compara dois produtos, podendo ser de empresas diferentes. RN12 / P26.
        """
        if not isinstance(produto_a, Produto) or not isinstance(produto_b, Produto):
            raise ValueError("Os dois argumentos devem ser produtos.")
        return {
            "produto_a": str(produto_a),
            "produto_b": str(produto_b),
            "empresa_a": produto_a.empresa.nome,
            "empresa_b": produto_b.empresa.nome,
            "diferenca_preco": produto_a.preco - produto_b.preco,
            "diferenca_estoque": (
                produto_a.quantidade_disponivel - produto_b.quantidade_disponivel
            ),
            "avaliacao_empresa_a": produto_a.empresa.media_avaliacoes(),
            "avaliacao_empresa_b": produto_b.empresa.media_avaliacoes(),
        }

    # -----------------------------------------------------------------------
    # Pedidos
    # -----------------------------------------------------------------------
    def realizar_pedido(
        self,
        empresa_marisqueira: EmpresaMarisqueira,
        endereco_entrega: str,
        tempo_entrega: str,
    ) -> "Pedido":
        """
        Cria um novo pedido. RN13, RN14.
        Um pedido é sempre destinado a uma única empresa marisqueira.
        """
        if not isinstance(empresa_marisqueira, EmpresaMarisqueira):
            raise ValueError("É necessário informar uma EmpresaMarisqueira.")
        pedido = Pedido(self, empresa_marisqueira, endereco_entrega, tempo_entrega)
        self.pedidos_realizados.append(pedido)
        return pedido

    # -----------------------------------------------------------------------
    # Avaliação
    # -----------------------------------------------------------------------
    def avaliar_empresa(
        self,
        empresa_marisqueira: EmpresaMarisqueira,
        nota: int,
        comentario: Optional[str] = None,
    ) -> "Avaliacao":
        """
        Avalia uma empresa marisqueira. RN21, P23, P24.
        Só é possível avaliar após a compra (pedido aceito ou posterior).
        """
        if not isinstance(empresa_marisqueira, EmpresaMarisqueira):
            raise ValueError("É necessário informar uma EmpresaMarisqueira.")

        tem_compra = any(
            p.empresa_marisqueira is empresa_marisqueira
            and p.status
            not in (
                StatusPedido.CRIADO,
                StatusPedido.RECEBIDO,
                StatusPedido.REJEITADO,
                StatusPedido.AJUSTE_SOLICITADO,
            )
            for p in self.pedidos_realizados
        )
        if not tem_compra:
            raise RegraNegocioError(
                "A empresa compradora só pode avaliar após a compra. RN21"
            )

        avaliacao = Avaliacao(self, empresa_marisqueira, nota, comentario)
        empresa_marisqueira.registrar_avaliacao(avaliacao)
        self.avaliacoes_feitas.append(avaliacao)
        return avaliacao


# ===========================================================================
# PRODUTO
# ===========================================================================
class Produto:
    """
    Produto comercializado por uma EmpresaMarisqueira.
    RN04, RN05, RN06, RN07, RN08, RN09, RN17, RN18, RN19, RN20.
    """

    def __init__(
        self,
        nome: str,
        categoria: CategoriaProduto,
        preco: float,
        quantidade_disponivel: int,
        empresa: EmpresaMarisqueira,
        foto: Optional[str] = None,
    ):
        if not nome or not isinstance(nome, str):
            raise ValueError("Nome do produto é obrigatório.")
        if not isinstance(categoria, CategoriaProduto):
            raise ValueError("Categoria inválida. Use CategoriaProduto.")
        if preco <= 0:
            raise ValueError("Preço deve ser maior que zero. RN07")
        if not isinstance(empresa, EmpresaMarisqueira):
            raise ValueError("Produto deve pertencer a uma EmpresaMarisqueira.")
        if quantidade_disponivel < 0:
            raise ValueError("Quantidade não pode ser negativa.")
        # RN05: quantidade mínima para comercialização é 25 kg.
        # No cadastro inicial, aceitamos >= 25 kg ou 0 (indisponível).
        if 0 < quantidade_disponivel < 25:
            raise QuantidadeMinimaError(
                "Quantidade mínima de cadastro é 25 kg (ou 0 para indisponível). RN05"
            )

        self.nome = nome
        self.categoria = categoria
        self.preco = preco
        self.quantidade_disponivel = quantidade_disponivel
        self.empresa = empresa
        self.foto = foto  # único campo opcional (P15)

    # -----------------------------------------------------------------------
    # Estoque
    # -----------------------------------------------------------------------
    def alterar_quantidade(self, nova_quantidade: int) -> None:
        """
        Altera a quantidade disponível. RN08, RN09.
        Pode ser 0 (produto continua cadastrado como indisponível).
        """
        if nova_quantidade < 0:
            raise ValueError("Quantidade não pode ser negativa.")
        self.quantidade_disponivel = nova_quantidade

    # Alias para atender à lista de métodos da atividade
    atualizar_quantidade = alterar_quantidade

    def verificar_disponibilidade(self, quantidade: int) -> bool:
        """RN17, RN18: verifica se há estoque suficiente."""
        if quantidade < 0:
            raise ValueError("Quantidade deve ser positiva.")
        return self.quantidade_disponivel >= quantidade

    def esta_disponivel(self) -> bool:
        """RN09, RN20: produto disponível se quantidade > 0."""
        return self.quantidade_disponivel > 0

    def __str__(self) -> str:
        return (
            f"{self.nome} ({self.categoria.value}) - "
            f"R$ {self.preco:.2f}/kg - {self.quantidade_disponivel} kg - "
            f"Empresa: {self.empresa.nome}"
        )


# ===========================================================================
# ITEM PEDIDO
# ===========================================================================
class ItemPedido:
    """
    Item de um pedido. RN05, RN07, RN15, RN17, RN18.
    """

    def __init__(self, produto: Produto, quantidade: int):
        if not isinstance(produto, Produto):
            raise ValueError("Produto inválido.")
        self.produto = produto
        self.quantidade = quantidade
        # RN07: preço fixado no momento da compra.
        self.preco_unitario = produto.preco

        self.validar_quantidade()
        self.verificar_disponibilidade()

    def validar_quantidade(self) -> None:
        """RN05, RN15: mínimo de 25 kg por produto."""
        if self.quantidade < 25:
            raise QuantidadeMinimaError(
                "Quantidade mínima por produto é de 25 kg. RN15"
            )

    def verificar_disponibilidade(self) -> None:
        """RN17, RN18: quantidade limitada ao estoque disponível."""
        if not self.produto.verificar_disponibilidade(self.quantidade):
            raise EstoqueInsuficienteError(
                f"Quantidade indisponível para '{self.produto.nome}'. "
                f"Solicitado: {self.quantidade} kg, "
                f"Disponível: {self.produto.quantidade_disponivel} kg."
            )

    def subtotal(self) -> float:
        return self.preco_unitario * self.quantidade

    def __str__(self) -> str:
        return (
            f"{self.produto.nome} ({self.produto.categoria.value}) - "
            f"{self.quantidade} kg x R$ {self.preco_unitario:.2f} = "
            f"R$ {self.subtotal():.2f}"
        )


# ===========================================================================
# PEDIDO
# ===========================================================================
class Pedido:
    """
    Pedido de uma EmpresaCompradora para uma EmpresaMarisqueira.
    RN07, RN13, RN14, RN15, RN17, RN18, RN21, RN22.
    """

    def __init__(
        self,
        empresa_compradora: EmpresaCompradora,
        empresa_marisqueira: EmpresaMarisqueira,
        endereco_entrega: str,
        tempo_entrega: str,
    ):
        if not isinstance(empresa_compradora, EmpresaCompradora):
            raise ValueError("Empresa compradora inválida. RN13")
        if not isinstance(empresa_marisqueira, EmpresaMarisqueira):
            raise ValueError("Empresa marisqueira inválida. RN14")
        if not endereco_entrega:
            raise ValueError("Endereço de entrega é obrigatório. RN13")
        if not tempo_entrega:
            raise ValueError("Tempo de entrega é obrigatório. RN13")

        self.empresa_compradora = empresa_compradora
        self.empresa_marisqueira = empresa_marisqueira
        self.endereco_entrega = endereco_entrega
        self.tempo_entrega = tempo_entrega

        self.itens: List[ItemPedido] = []
        self.status = StatusPedido.CRIADO
        self.motivo_rejeicao: Optional[str] = None
        self.mensagem_ajuste: Optional[str] = None
        self.criado_em = datetime.now()

    # -----------------------------------------------------------------------
    # Itens
    # -----------------------------------------------------------------------
    def adicionar_item(self, produto: Produto, quantidade: int) -> None:
        """
        Adiciona um item ao pedido. RN14, RN15, RN28.
        Um pedido não pode reunir produtos de empresas diferentes.
        """
        if produto.empresa is not self.empresa_marisqueira:
            raise RegraNegocioError(
                "Um pedido não pode reunir produtos de empresas diferentes. RN14"
            )
        item = ItemPedido(produto, quantidade)
        self.itens.append(item)

    def validar_quantidade(self) -> None:
        """RN15: valida quantidade de todos os itens."""
        if not self.itens:
            raise RegraNegocioError("Pedido deve ter pelo menos um item. RN13")
        for item in self.itens:
            item.validar_quantidade()

    def verificar_disponibilidade(self) -> None:
        """RN17, RN18: verifica estoque de todos os itens."""
        for item in self.itens:
            item.verificar_disponibilidade()

    def calcular_total(self) -> float:
        return sum(item.subtotal() for item in self.itens)

    # -----------------------------------------------------------------------
    # Ciclo de vida
    # -----------------------------------------------------------------------
    def receber_pedido(self) -> None:
        """Marca o pedido como recebido pela marisqueira."""
        self.status = StatusPedido.RECEBIDO

    def aceitar_pedido(self) -> None:
        """
        Aceita o pedido e dá baixa no estoque.
        RN07 (preço não muda), RN08, RN18.
        """
        self.verificar_disponibilidade()
        for item in self.itens:
            nova_qtd = item.produto.quantidade_disponivel - item.quantidade
            item.produto.alterar_quantidade(nova_qtd)
        self.status = StatusPedido.ACEITO

    def rejeitar_pedido(self, motivo: str = "") -> None:
        self.status = StatusPedido.REJEITADO
        self.motivo_rejeicao = motivo

    def solicitar_ajuste(self, mensagem: str) -> None:
        self.status = StatusPedido.AJUSTE_SOLICITADO
        self.mensagem_ajuste = mensagem

    def atualizar_status_entrega(self, novo_status: StatusPedido) -> None:
        """RN22: apenas atualização de status, sem rastreamento em tempo real."""
        permitidos = {
            StatusPedido.EM_PREPARACAO,
            StatusPedido.EM_ENTREGA,
            StatusPedido.ENTREGUE,
        }
        if novo_status not in permitidos:
            raise ValueError(
                f"Status de entrega inválido. Permitidos: "
                f"{[s.value for s in permitidos]}"
            )
        self.status = novo_status

    def __str__(self) -> str:
        itens_str = "\n".join(f"  - {item}" for item in self.itens) or "  (sem itens)"
        return (
            f"Pedido #{id(self)} | Status: {self.status.value}\n"
            f"Comprador: {self.empresa_compradora}\n"
            f"Marisqueira: {self.empresa_marisqueira}\n"
            f"Endereço: {self.endereco_entrega}\n"
            f"Tempo de entrega: {self.tempo_entrega}\n"
            f"Itens:\n{itens_str}\n"
            f"Total: R$ {self.calcular_total():.2f}"
        )


# ===========================================================================
# AVALIAÇÃO
# ===========================================================================
class Avaliacao:
    """
    Avaliação de uma EmpresaMarisqueira por uma EmpresaCompradora.
    RN21, P23, P24.
    """

    def __init__(
        self,
        empresa_compradora: EmpresaCompradora,
        empresa_marisqueira: EmpresaMarisqueira,
        nota: int,
        comentario: Optional[str] = None,
    ):
        if not isinstance(empresa_compradora, EmpresaCompradora):
            raise ValueError("Empresa compradora inválida. RN21")
        if not isinstance(empresa_marisqueira, EmpresaMarisqueira):
            raise ValueError("Empresa marisqueira inválida. RN21")

        self.empresa_compradora = empresa_compradora
        self.empresa_marisqueira = empresa_marisqueira
        self.comentario = comentario
        self.data = datetime.now()
        self.nota: int = 0
        self.registrar_nota(nota)

    def registrar_nota(self, nota: int) -> None:
        """RN21, P24: nota inteira de 1 a 5 estrelas."""
        if not isinstance(nota, int) or nota < 1 or nota > 5:
            raise ValueError("Nota deve ser um inteiro de 1 a 5 estrelas. P24")
        self.nota = nota

    def __str__(self) -> str:
        return (
            f"Avaliação de {self.empresa_marisqueira.nome} por "
            f"{self.empresa_compradora.nome}: {self.nota}★ "
            f"({self.comentario or 'sem comentário'})"
        )


# ===========================================================================
# DEMONSTRAÇÃO (opcional — apague se não precisar)
# ===========================================================================
if __name__ == "__main__":
    marisqueira = EmpresaMarisqueira(
        nome="Marisqueira da Vila",
        localizacao="Raposa - MA",
        responsavel="Dona Maria",
        horario_funcionamento=(8, 18),
    )
    compradora = EmpresaCompradora(
        nome="Restaurante Maré",
        localizacao="São Luís - MA",
        responsavel="Sr. João",
        horario_funcionamento=(9, 22),
    )

    # Cadastro de produtos (fresco e congelado como itens diferentes — RN06)
    camarao_fresco = marisqueira.cadastrar_produto(
        "Camarão", CategoriaProduto.FRESCO, 45.0, 100
    )
    camarao_congelado = marisqueira.cadastrar_produto(
        "Camarão", CategoriaProduto.CONGELADO, 38.0, 80
    )

    # Consulta
    print("Consulta (fresco, ordenado por menor preço):")
    for p in compradora.consultar_produtos(
        marisqueira.consultar_proprios_produtos(),
        categoria=CategoriaProduto.FRESCO,
        ordenar_por="menor_preco",
    ):
        print(" -", p)

    # Comparação
    print("\nComparação:")
    print(compradora.comparar_produtos(camarao_fresco, camarao_congelado))

    # Pedido
    pedido = compradora.realizar_pedido(
        marisqueira, endereco_entrega="Rua das Conchas, 100", tempo_entrega="2 dias"
    )
    pedido.adicionar_item(camarao_fresco, 50)
    pedido.adicionar_item(camarao_congelado, 30)

    marisqueira.receber_pedido(pedido)
    marisqueira.aceitar_pedido(pedido)
    marisqueira.atualizar_status_entrega(pedido, StatusPedido.EM_PREPARACAO)
    marisqueira.atualizar_status_entrega(pedido, StatusPedido.EM_ENTREGA)
    marisqueira.atualizar_status_entrega(pedido, StatusPedido.ENTREGUE)

    print("\nPedido finalizado:")
    print(pedido)

    # Avaliação
    avaliacao = compradora.avaliar_empresa(marisqueira, 5, "Produto fresco e ótimo")
    print("\n", avaliacao)
    print("Média da marisqueira:", marisqueira.media_avaliacoes())
    print("Status visual:", marisqueira.status_visual().value)
