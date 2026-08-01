"""Gerador do feed XML VRSync (009-integracao-portais).

Schema real obtido em developers.grupozap.com/feeds/vrsync/* (Portal de Integração do Grupo
OLX) — ver specs/009-integracao-portais/data-model.md para o mapeamento completo e as fontes.
Função pura: recebe imóveis já filtrados (RN2) e devolve uma string XML, sem tocar banco.
"""

import json
from datetime import datetime, timezone
from decimal import Decimal
from xml.etree.ElementTree import Element, SubElement, tostring

from app.modules.imoveis.models import Finalidade, Imovel, ImovelTipo

_NAMESPACE = "http://www.vivareal.com/schemas/1.0/VRSync"
_SCHEMA_LOCATION = "http://xml.vivareal.com/vrsync.xsd"

# Mapeamento ImovelTipo -> (UsageType, PropertyType) — valores exatos confirmados na
# documentação; onde ImovelTipo não tem granularidade fina, uso o valor mais genérico aplicável.
_TIPO_PARA_VRSYNC: dict[ImovelTipo, tuple[str, str]] = {
    ImovelTipo.APARTAMENTO: ("Residential", "Residential / Apartment"),
    ImovelTipo.CASA: ("Residential", "Residential / Home"),
    ImovelTipo.TERRENO: ("Residential", "Residential / Land Lot"),
    ImovelTipo.COMERCIAL: ("Commercial", "Commercial / Business"),
    ImovelTipo.GALPAO: ("Commercial", "Commercial / Industrial"),
}

_FINALIDADE_PARA_TRANSACTION_TYPE = {
    Finalidade.VENDA: "For Sale",
    Finalidade.ALUGUEL: "For Rent",
}


def _texto(parent: Element, tag: str, valor: str | None) -> None:
    if valor is None or valor == "":
        return
    el = SubElement(parent, tag)
    el.text = valor


def _preco(parent: Element, tag: str, valor: Decimal, *, periodo: str | None = None) -> None:
    el = SubElement(parent, tag, {"currency": "BRL"})
    if periodo is not None:
        el.set("period", periodo)
    el.text = str(valor)


def _monta_listing(imovel: Imovel, *, base_url: str) -> Element:
    usage_type, property_type = _TIPO_PARA_VRSYNC[imovel.tipo]
    listing = Element("Listing")

    _texto(listing, "ListingID", str(imovel.uuid))
    _texto(listing, "Title", imovel.titulo)
    _texto(listing, "TransactionType", _FINALIDADE_PARA_TRANSACTION_TYPE[imovel.finalidade])

    location = SubElement(listing, "Location")
    _texto(location, "Country", "Brazil")
    _texto(location, "State", imovel.estado)
    _texto(location, "City", imovel.cidade)
    _texto(location, "Neighborhood", imovel.bairro)
    _texto(listing, "PostalCode", imovel.cep)

    media = SubElement(listing, "Media")
    for i, url in enumerate(json.loads(imovel.fotos)):
        item = SubElement(media, "Item", {"medium": "image"})
        if i == 0:
            item.set("primary", "true")
        item.text = f"{base_url}{url}"

    contact_info = SubElement(listing, "ContactInfo")
    _texto(contact_info, "Name", imovel.titulo)

    details = SubElement(listing, "Details")
    _texto(details, "UsageType", usage_type)
    _texto(details, "PropertyType", property_type)
    if imovel.descricao:
        _texto(details, "Description", imovel.descricao)
    if imovel.area_total is not None:
        area = SubElement(details, "LivingArea", {"unit": "square metres"})
        area.text = str(imovel.area_total)
    if imovel.valor_anunciado is not None:
        if imovel.finalidade == Finalidade.ALUGUEL:
            _preco(details, "RentalPrice", imovel.valor_anunciado, periodo="Monthly")
        else:
            _preco(details, "ListPrice", imovel.valor_anunciado)
    if imovel.quartos is not None:
        _texto(details, "Bedrooms", str(imovel.quartos))
    if imovel.banheiros is not None:
        _texto(details, "Bathrooms", str(imovel.banheiros))
    if imovel.suites is not None:
        _texto(details, "Suites", str(imovel.suites))
    if imovel.vagas is not None:
        _texto(details, "Garage", str(imovel.vagas))

    return listing


def gerar_feed_vrsync(
    imoveis: list[Imovel], *, provider: str, email: str, contact_name: str, base_url: str = ""
) -> str:
    """Gera o XML do feed VRSync. `imoveis` já deve vir filtrado (RN2: disponível + ativo +
    finalidade definida + ao menos 1 foto) — esta função não filtra nada, só serializa.
    `base_url` (ex.: `https://{slug}.dominio.com.br`) prefixa as URLs de `Media` — o Grupo OLX
    busca essas imagens de fora, então precisam ser absolutas, nunca relativas."""
    root = Element(
        "ListingDataFeed",
        {
            "xmlns": _NAMESPACE,
            "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "xsi:schemaLocation": f"{_NAMESPACE} {_SCHEMA_LOCATION}",
        },
    )

    header = SubElement(root, "Header")
    _texto(header, "Provider", provider)
    _texto(header, "Email", email)
    _texto(header, "ContactName", contact_name)
    _texto(header, "PublishDate", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"))

    listings = SubElement(root, "Listings")
    for imovel in imoveis:
        listings.append(_monta_listing(imovel, base_url=base_url))

    return '<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(root, encoding="unicode")
