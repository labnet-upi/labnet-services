from fastapi import APIRouter, Query, Depends
from core.auth import get_current_user
from typing import List
from utils.database import db, convert_objectid
from services.tugas_besar import getNilaiPerKelompok, getAspekPenilaianPerorangan, extract_children_only
from utils.generate_file_response import generate_csv_response, generate_excel_response
from bson import ObjectId

router = APIRouter(dependencies=[Depends(get_current_user)])

@router.get("/nilai-kelompok")
async def get_rekap_nilai_kelompok(
    tahun: List[int] = Query(...), 
    kelas: List[str] = Query(...),
    format: str = Query("json")
):
    doc_kelompok_tubes = await getNilaiPerKelompok(tahun, kelas)

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
            doc_nilai_perorangan = await db.nilai_perorangan.find({"id_mahasiswa": ObjectId(anggota_item["id"])}).to_list(length=None)
            nilai_kelompok = kelompok.get("nilaiAkhir", 0)
            nilai_perorangan = 0
            if not doc_nilai_perorangan:
                nilaiAkhir = (nilai_perorangan + nilai_kelompok) / 2
                doc_rekap_nilai_perorangan.append({
                    "nama": anggota_item["nama"],
                    "nim": anggota_item["nim"],
                    "kelas": kelompok["kelas"],
                    "tahun": kelompok["tahun"],
                    "nomor": kelompok["nomor"],
                    "nilaiPerorangan": 0,
                    "nilaiKelompok": nilai_kelompok,
                    "nilaiAkhir": nilaiAkhir
                })
                continue

            nilai_perorangan = 0
            jumlah_panelis = 0
            for nilai_panelis in doc_nilai_perorangan:
                jumlah_panelis += 1

                nilai_akhir_panelis = 0
                item_nilai = convert_objectid(nilai_panelis.get("nilai", []))
                for item in item_nilai:
                    # cari bobot dari aspek penilaian
                    bobot = next((ap["bobot"] for ap in doc_aspek_penilaian_perorangan if ap["id"] == item["aspek_penilaian_id"]), 0)
                    # jumlahkan nilai akhir
                    nilai_akhir_panelis += (item["nilai"] * bobot / 100)
                
                nilai_perorangan += nilai_akhir_panelis
                del nilai_panelis["nilai"]

            nilai_perorangan = (nilai_perorangan / jumlah_panelis) if jumlah_panelis > 0 else 0
            nilaiAkhir = (nilai_perorangan + nilai_kelompok) / 2
            
            doc_rekap_nilai_perorangan.append({
                "nama": anggota_item["nama"],
                "nim": anggota_item["nim"],
                "kelas": kelompok["kelas"],
                "tahun": kelompok["tahun"],
                "nomor": kelompok["nomor"],
                "nilaiPerorangan": nilai_perorangan,
                "nilaiKelompok": nilai_kelompok,
                "nilaiAkhir": nilaiAkhir
            })

    if format == "csv":
        return generate_csv_response(doc_rekap_nilai_perorangan, filename="rekap_nilai.csv")
    elif format == "excel":
        return generate_excel_response(doc_rekap_nilai_perorangan, filename="rekap_nilai.xlsx", sheet_name="Nilai")
    else:
        return doc_rekap_nilai_perorangan