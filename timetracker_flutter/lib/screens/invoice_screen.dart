import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../services/db_service.dart';
import '../models/entry.dart';

class InvoiceScreen extends StatefulWidget {
  const InvoiceScreen({super.key});
  @override
  State<InvoiceScreen> createState() => _InvoiceScreenState();
}

class _InvoiceScreenState extends State<InvoiceScreen> {
  List<String>  _labels      = [];
  String?       _selectedLabel;
  final _rateCtrl = TextEditingController();
  String        _status      = '';

  @override
  void initState() {
    super.initState();
    _loadLabels();
  }

  @override
  void dispose() {
    _rateCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadLabels() async {
    final labels = await DbService.distinctLabels();
    setState(() {
      _labels = labels;
      if (_labels.isNotEmpty) _selectedLabel = _labels.first;
    });
  }

  Future<void> _generate() async {
    final rate = double.tryParse(_rateCtrl.text.trim().replaceAll('\$', ''));
    if (rate == null || rate < 0) {
      setState(() => _status = 'Enter a valid hourly rate.');
      return;
    }
    if (_selectedLabel == null) {
      setState(() => _status = 'Select a project label.');
      return;
    }
    final entries = await DbService.entriesByLabel(_selectedLabel!);
    if (entries.isEmpty) {
      setState(() => _status = 'No entries for "$_selectedLabel".');
      return;
    }
    final totalSecs = entries.fold<int>(0, (s, e) => s + e.durationSecs);
    final totalHrs  = totalSecs / 3600;
    final totalAmt  = totalHrs * rate;

    setState(() => _status = 'Generated! Total: \$${totalAmt.toStringAsFixed(2)}');
    // TODO: wire up the `pdf` package to build and share/print the invoice PDF.
    // Use the same layout as the Python _build_invoice_pdf for consistency.
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('CREATE INVOICE'),
        leading: BackButton(onPressed: () => context.pop()),
        actions: [
          IconButton(
            icon: const Icon(Icons.home),
            tooltip: 'Home',
            onPressed: () => context.go('/'),
          ),
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text('Project / Client', style: TextStyle(color: Color(0xFF8A8AA0))),
            const SizedBox(height: 6),
            if (_labels.isEmpty)
              const Text('No labeled entries found.',
                  style: TextStyle(color: Color(0xFF8A8AA0)))
            else
              DropdownButton<String>(
                value: _selectedLabel,
                dropdownColor: const Color(0xFF0F3460),
                isExpanded: true,
                items: _labels
                    .map((l) => DropdownMenuItem(value: l, child: Text(l)))
                    .toList(),
                onChanged: (v) => setState(() => _selectedLabel = v),
              ),
            const SizedBox(height: 20),
            TextField(
              controller: _rateCtrl,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              decoration: const InputDecoration(
                labelText: 'Hourly Rate (\$)',
                labelStyle: TextStyle(color: Color(0xFF8A8AA0)),
                prefixText: '\$ ',
              ),
              style: const TextStyle(color: Colors.white),
            ),
            const SizedBox(height: 24),
            ElevatedButton(
              onPressed: _generate,
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF27AE60),
                padding: const EdgeInsets.symmetric(vertical: 14),
              ),
              child: const Text('Generate Invoice PDF',
                  style: TextStyle(fontWeight: FontWeight.bold)),
            ),
            if (_status.isNotEmpty) ...[
              const SizedBox(height: 12),
              Text(_status, style: const TextStyle(color: Color(0xFF8A8AA0))),
            ],
          ],
        ),
      ),
    );
  }
}
