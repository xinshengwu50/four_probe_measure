"""Check separately captured transactions; config and read may have different lengths."""
from spi_contract import SpiConfig, validate_trace

def validate_transactions(transactions):
    if not transactions:
        raise ValueError('empty transaction list')
    results = []
    for item in transactions:
        config = SpiConfig(**item['spi'])
        result = validate_trace(item['trace'], config, item['tx'], item['rx'])
        results.append({'name': item['name'], 'check': result})
    return {'passed': all(x['check']['passed'] for x in results),
            'transactions': results, 'evidence': 'DIGITAL_TRACE_ONLY', 'hardware_verified': False}
