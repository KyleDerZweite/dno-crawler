

def main():
    search_string = "50859 Köln An Der Ronne 160"
    types = ["netzentgelte", "hlzf"]    
    years = [2024, 2025]
    
    assert_resulting_queries = [
        "50859 Köln Netzbetreiber",
    ]
    assert_query_result = {
        "dno_name": "RheinNetz",
        "slug": "rhein_netz",
        "website": "https://www.rheinnetz.de/",
    } # Or what ever needs to be actually in this object for the database

    pdf_retrival_queries = [
        "\"www.rheinnetz.de\" Netzentgelte 2024 filetype:pdf",
        "\"www.rheinnetz.de\" Netzentgelte 2025 filetype:pdf",
        "\"www.rheinnetz.de\" Hochlastzeitfenster 2024 filetype:pdf",
        "\"www.rheinnetz.de\" Hochlastzeitfenster 2025 filetype:pdf"
    ]

    assert_pdf_retrival_results = [
        {
            "url": "https://www.rheinnetz.de/netzentgelte-strom-ab-dem-01.01.2024.pdfx",
            "filetype": "table,pdf",
            "year": 2024,
            "dno": "RheinNetz",
            "slug": "rhein_netz",
            "type": "netzentgelte"
        },
        {
            "url": "https://www.rheinnetz.de/netzentgelte-strom-ab-dem-01.01.2025.pdfx",
            "filetype": "table, pdf",
            "year": 2025,
            "dno": "RheinNetz",
            "slug": "rhein_netz",
            "type": "netzentgelte"
        },
        {
            "url": "https://www.rheinnetz.de/netzentgelte-strom",
            "filetype": "table, website",
            "year": 2024,
            "dno": "RheinNetz",
            "slug": "rhein_netz",
            "type": "hochlastzeitfenster"
        },
        {
            "url": "https://www.rheinnetz.de/netzentgelte-strom",
            "filetype": "table, website",
            "year": 2025,
            "dno": "RheinNetz",
            "slug": "rhein_netz",
            "type": "hochlastzeitfenster"
        }
    ]   

    # TODO: To be tested against the actuall function!




if __name__ == "__main__":
    main()
