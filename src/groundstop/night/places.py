"""Real airports, fictional airlines, generated passengers.

Fragata (the hub airline), Garoa Linhas Aéreas (the partner) and Hoteles Ondelia are fictional.
Passenger names are random combinations of common first names and surnames, not real people.
"""

from __future__ import annotations

HUB = "PTY"

# IATA code → (city, language most passengers to it speak)
DESTINATIONS: dict[str, tuple[str, str]] = {
    "BOG": ("Bogotá", "es"),
    "MDE": ("Medellín", "es"),
    "CLO": ("Cali", "es"),
    "CTG": ("Cartagena", "es"),
    "LIM": ("Lima", "es"),
    "UIO": ("Quito", "es"),
    "GYE": ("Guayaquil", "es"),
    "SCL": ("Santiago", "es"),
    "EZE": ("Buenos Aires", "es"),
    "MVD": ("Montevideo", "es"),
    "ASU": ("Asunción", "es"),
    "VVI": ("Santa Cruz de la Sierra", "es"),
    "GRU": ("São Paulo", "pt"),
    "GIG": ("Río de Janeiro", "pt"),
    "BSB": ("Brasilia", "pt"),
    "POA": ("Porto Alegre", "pt"),
    "CNF": ("Belo Horizonte", "pt"),
    "MAO": ("Manaos", "pt"),
    "SJO": ("San José", "es"),
    "SAL": ("San Salvador", "es"),
    "GUA": ("Ciudad de Guatemala", "es"),
    "MGA": ("Managua", "es"),
    "SAP": ("San Pedro Sula", "es"),
    "MEX": ("Ciudad de México", "es"),
    "CUN": ("Cancún", "es"),
    "GDL": ("Guadalajara", "es"),
    "HAV": ("La Habana", "es"),
    "SDQ": ("Santo Domingo", "es"),
    "PUJ": ("Punta Cana", "es"),
    "SJU": ("San Juan", "es"),
    "MIA": ("Miami", "en"),
    "MCO": ("Orlando", "en"),
    "JFK": ("Nueva York", "en"),
    "LAX": ("Los Ángeles", "en"),
    "IAD": ("Washington", "en"),
    "YYZ": ("Toronto", "en"),
}

# Garoa flies from Tocumen to these three; its seats are open to Fragata passengers with an interline fare.
GAROA = ("GRU", "GIG", "BSB")

HOTELS = ("Ondelia Tocumen", "Ondelia Costa del Este", "Ondelia Vía España", "Ondelia Albrook")

FIRST = {
    "es": (
        "María José Ana Luis Carmen Carlos Lucía Jorge Valentina Andrés Camila Diego Sofía Javier Daniela "
        "Miguel Paula Fernando Gabriela Ricardo Isabel Alejandro Mariana Pablo Natalia Sebastián Elena Mateo "
        "Rosa Tomás Julia Héctor Adriana Raúl Claudia Emilio Teresa Felipe Lorena Óscar"
    ).split(),
    "pt": (
        "João Maria Ana Pedro Lucas Juliana Mateus Beatriz Gabriel Larissa Rafael Fernanda Gustavo Camila "
        "Thiago Letícia Bruno Aline Felipe Mariana Rodrigo Patrícia Diego Renata Leonardo Carolina Vinícius "
        "Bianca Eduardo Tatiana"
    ).split(),
    "en": (
        "James Mary John Patricia Robert Jennifer Michael Linda David Emily Daniel Sarah Matthew Laura Andrew "
        "Rachel Joshua Megan Ryan Hannah Kevin Olivia"
    ).split(),
}
LAST = {
    "es": (
        "García Rodríguez Martínez López González Pérez Sánchez Ramírez Torres Flores Rivera Gómez Díaz "
        "Morales Ortiz Castillo Rojas Vargas Herrera Medina Castro Jiménez Ruiz Mendoza Aguilar Silva Navarro "
        "Romero Suárez Quintero Salazar Cárdenas Paredes Espinoza Valencia Cabrera Ríos Molina Fuentes Campos"
    ).split(),
    "pt": (
        "Silva Santos Oliveira Souza Rodrigues Ferreira Alves Pereira Lima Gomes Costa Ribeiro Martins "
        "Carvalho Almeida Lopes Soares Fernandes Vieira Barbosa Rocha Dias Nascimento Andrade Moreira Nunes "
        "Mendes Freitas Cardoso Teixeira"
    ).split(),
    "en": (
        "Smith Johnson Williams Brown Jones Miller Davis Wilson Anderson Taylor Thomas Moore Martin Thompson "
        "White Harris Clark Lewis Walker Young"
    ).split(),
}
