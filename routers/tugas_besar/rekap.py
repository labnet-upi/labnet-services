from fastapi import APIRouter, Query, Depends
from auth import get_current_user
from typing import List
from utils.database import db, convert_objectid
from services.tugas_besar import getNilaiPerKelompok, getAspekPenilaianPerorangan, extract_children_only
from utils.generate_file_response import generate_csv_response, generate_excel_response

router = APIRouter(dependencies=[Depends(get_current_user)])

@router.get("/nilai-kelompok")
async def get_rekap_nilai_kelompok(
    tahun: List[int] = Query(...), 
    kelas: List[str] = Query(...),
    format: str = Query("json")
):
    doc_kelompok_tubes = await getNilaiPerKelompok(tahun, kelas)
    doc_kelompok_tubes = sorted(doc_kelompok_tubes, key=lambda x: x["nilaiAkhir"], reverse=True)

    if format == "csv":
        return generate_csv_response(doc_kelompok_tubes, filename="rekap_nilai.csv")
    elif format == "excel":
        return generate_excel_response(doc_kelompok_tubes, filename="rekap_nilai.xlsx", sheet_name="Nilai")
    else:
        return doc_kelompok_tubes

@router.get("/nilai-perorangan")
async def get_rekap_nilai_perorangan(
    tahun: List[int] = Query(...), 
    kelas: List[str] = Query(...),
    format: str = Query("json")
):
    doc_kelompok_tubes = await getNilaiPerKelompok(tahun, kelas)
    doc_aspek_penilaian_perorangan = await getAspekPenilaianPerorangan(tahun)
    doc_aspek_penilaian_perorangan = extract_children_only(doc_aspek_penilaian_perorangan)

    doc_rekap_nilai_perorangan = []
    for kelompok in doc_kelompok_tubes:
        anggota = kelompok.get("anggota", [])
        for anggota_item in anggota:
            # ambil nilai perorangan
            doc_nilai_perorangan = await db.nilai_perorangan.find_one({"nim": anggota_item["nim"]})
            nilai_kelompok = kelompok.get("nilaiAkhir", 0)
            nilai_perorangan = 0
            if not doc_nilai_perorangan:
                nilaiAkhir = (nilai_perorangan + nilai_kelompok) / 2
                doc_rekap_nilai_perorangan.append({
                    "nama": anggota_item["nama"],
                    "nim": anggota_item["nim"],
                    "kelas": kelompok["kelas"],
                    "angkatan": kelompok["angkatan"],
                    "nomor": kelompok["nomor"],
                    "nilaiPerorangan": 0,
                    "nilaiKelompok": nilai_kelompok,
                    "nilaiAkhir": nilaiAkhir
                })
                continue
            
            # konversi nilai perorangan
            data_nilai_perorangan = convert_objectid(doc_nilai_perorangan.get("nilai", []))
            for item in data_nilai_perorangan:
                # cari bobot dari aspek penilaian
                bobot = next((ap["bobot"] for ap in doc_aspek_penilaian_perorangan if ap["id"] == item["aspek_penilaian_id"]), 0)
                # jumlahkan nilai akhir
                nilai_perorangan += (item["nilai"] * bobot / 100)

            nilaiAkhir = (nilai_perorangan + nilai_kelompok) / 2
            doc_rekap_nilai_perorangan.append({
                "nama": anggota_item["nama"],
                "nim": anggota_item["nim"],
                "kelas": kelompok["kelas"],
                "angkatan": kelompok["angkatan"],
                "nomor": kelompok["nomor"],
                "nilaiPerorangan": nilai_perorangan,
                "nilaiKelompok": nilai_kelompok,
                "nilaiAkhir": nilaiAkhir
            })
    doc_rekap_nilai_perorangan = sorted(doc_rekap_nilai_perorangan, key=lambda x: x["nilaiAkhir"], reverse=True)

    if format == "csv":
        return generate_csv_response(doc_rekap_nilai_perorangan, filename="rekap_nilai.csv")
    elif format == "excel":
        return generate_excel_response(doc_rekap_nilai_perorangan, filename="rekap_nilai.xlsx", sheet_name="Nilai")
    else:
        return doc_rekap_nilai_perorangan