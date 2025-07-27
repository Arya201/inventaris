$(function () {
    // Tambah barang
    $('#formTambah').submit(function (e) {
        e.preventDefault();
        let data = {
            nama: $('input[name="nama"]').val(),
            satuan: $('input[name="satuan"]').val(),
            harga: $('input[name="harga"]').val(),
            qty: $('input[name="qty"]').val()
        };
        $.post('/barang', JSON.stringify(data), function () {
            location.reload();
        }, 'json');
    });

    // Update barang
    $('.update-btn').click(function () {
        let row = $(this).closest('tr');
        let id = row.data('id');
        let data = {
            nama: row.find('.edit-nama').val(),
            satuan: row.find('.edit-satuan').val(),
            harga: row.find('.edit-harga').val()
        };
        $.ajax({
            url: '/barang/' + id,
            type: 'PUT',
            contentType: 'application/json',
            data: JSON.stringify(data),
            success: function () {
                alert('Berhasil update');
                location.reload();
            }
        });
    });

    // Hapus barang
    $('.delete-btn').click(function () {
        if (!confirm('Hapus barang ini?')) return;
        let id = $(this).closest('tr').data('id');
        $.ajax({
            url: '/barang/' + id,
            type: 'DELETE',
            success: function () {
                location.reload();
            }
        });
    });

    // Simpan transaksi
    $('#formTransaksi').submit(function (e) {
        e.preventDefault();
        let data = {
            tanggal: $('input[name="tanggal"]').val(),
            id_barang: $('select[name="id_barang"]').val(),
            barang_masuk: $('input[name="barang_masuk"]').val() || 0,
            barang_keluar: $('input[name="barang_keluar"]').val() || 0,
            keterangan: $('input[name="keterangan"]').val()
        };
        $.post('/transaksi', JSON.stringify(data), function () {
            location.reload();
        }, 'json');
    });
});
