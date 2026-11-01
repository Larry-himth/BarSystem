   import 'package:flutter/material.dart';
  import 'dart:convert';
  import 'dart:io';

   void main() => runApp(const MaterialApp(home: Hello()));

   class Hello extends StatefulWidget {
     const Hello({super.key});
     @override
     State<Hello> createState() => _HelloState();
   }

   class _HelloState extends State<Hello> {
     final url = TextEditingController(text: 'http://192.168.0.10:8000');
     String result = 'not called yet';

     Future<void> call() async {
       setState(() => result = 'calling...');
       try {
         final client = HttpClient();
         try {
           final request = await client
               .getUrl(Uri.parse('${url.text}/api/v1/health/'))
               .timeout(const Duration(seconds: 8));
           final response = await request.close().timeout(const Duration(seconds: 8));
           final body = await response.transform(utf8.decoder).join();
           setState(() => result = '${response.statusCode}\n$body');
         } finally {
           client.close();
         }
       } catch (e) {
         setState(() => result = 'ERROR: $e');
       }
     }

     @override
     Widget build(BuildContext context) => Scaffold(
           appBar: AppBar(title: const Text('Bar API check')),
           body: Padding(
             padding: const EdgeInsets.all(16),
             child: Column(children: [
               TextField(
                 controller: url,
                 decoration: const InputDecoration(labelText: 'Server address'),
               ),
               const SizedBox(height: 12),
               ElevatedButton(onPressed: call, child: const Text('Call /health/')),
               const SizedBox(height: 12),
               Text(result),
             ]),
           ),
         );
   }