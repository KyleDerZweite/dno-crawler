"""
VNB Digital Module - GraphQL Queries.

GraphQL query definitions for VNB Digital API.
"""

SEARCH_QUERY = """
query ($searchTerm: String!) {
  vnb_search(searchTerm: $searchTerm) {
    _id
    title
    subtitle
    logo {
      url
    }
    url
    type
  }
}
"""

COORDINATES_QUERY = """
fragment vnb_Region on vnb_Region {
  _id
  name
  logo {
    url
  }
  bbox
  layerUrl
  slug
  vnbs {
    _id
  }
}

fragment vnb_VNB on vnb_VNB {
  _id
  name
  logo {
    url
  }
  services {
    type {
      name
      type
    }
    activated
  }
  bbox
  layerUrl
  types
  voltageTypes
}

query (
  $coordinates: String
  $filter: vnb_FilterInput
  $withCoordinates: Boolean = false
) {
  vnb_coordinates(coordinates: $coordinates) @include(if: $withCoordinates) {
    geometry
    regions(filter: $filter) {
      ...vnb_Region
    }
    vnbs(filter: $filter) {
      ...vnb_VNB
    }
  }
}
"""

VNB_DETAILS_QUERY = """
query ($id: ID!) {
  vnb_vnb(id: $id) {
    _id
    name
    address
    phone
    website
    contact
  }
}
"""
