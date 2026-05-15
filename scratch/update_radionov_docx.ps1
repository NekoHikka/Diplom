$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$root = Split-Path -Parent $PSScriptRoot
$docName = [string]::Concat([char[]](0x420,0x430,0x434,0x456,0x43E,0x43D,0x43E,0x432)) + '.docx'
$path = Join-Path $root $docName
$contentPath = Join-Path $PSScriptRoot 'radionov_content.txt'
$backup = Join-Path $root (($docName -replace '\.docx$','') + '_backup_rewrite_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.docx')
Copy-Item -LiteralPath $path -Destination $backup

$data = Get-Content -LiteralPath $contentPath -Raw -Encoding UTF8
$items = @()
foreach ($line in ([regex]::Split($data.Trim(), "`r?`n"))) {
    if ($line.Trim().Length -eq 0) { continue }
    $items += [pscustomobject]@{ Kind=$line.Substring(0,1); Text=$line.Substring(2) }
}

$wNs = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
$zip = [System.IO.Compression.ZipFile]::Open($path, [System.IO.Compression.ZipArchiveMode]::Update)
try {
    $entry = $zip.GetEntry('word/document.xml')
    $reader = [IO.StreamReader]::new($entry.Open())
    $xmlText = $reader.ReadToEnd()
    $reader.Close()
    [xml]$xml = $xmlText
    $ns = [Xml.XmlNamespaceManager]::new($xml.NameTable)
    $ns.AddNamespace('w', $wNs)
    $body = $xml.SelectSingleNode('//w:body', $ns)
    $sectPr = $body.SelectSingleNode('w:sectPr', $ns)
    @($body.ChildNodes) | ForEach-Object {
        if ($_.LocalName -ne 'sectPr') { [void]$body.RemoveChild($_) }
    }

    function New-WAttr([xml]$doc, [string]$name, [string]$value) {
        $attr = $doc.CreateAttribute('w', $name, $wNs)
        $attr.Value = $value
        return $attr
    }

    function Add-RunProps([xml]$doc, [System.Xml.XmlElement]$r, [bool]$bold, [bool]$italic, [string]$color) {
        $rPr = $doc.CreateElement('w','rPr',$wNs)
        $fonts = $doc.CreateElement('w','rFonts',$wNs)
        foreach ($n in @('ascii','hAnsi','eastAsia','cs')) {
            [void]$fonts.Attributes.Append((New-WAttr $doc $n 'Times New Roman'))
        }
        [void]$rPr.AppendChild($fonts)
        if ($bold) { [void]$rPr.AppendChild($doc.CreateElement('w','b',$wNs)) }
        if ($italic) { [void]$rPr.AppendChild($doc.CreateElement('w','i',$wNs)) }
        $c = $doc.CreateElement('w','color',$wNs)
        [void]$c.Attributes.Append((New-WAttr $doc 'val' $color))
        [void]$rPr.AppendChild($c)
        $sz = $doc.CreateElement('w','sz',$wNs)
        [void]$sz.Attributes.Append((New-WAttr $doc 'val' '28'))
        [void]$rPr.AppendChild($sz)
        $szCs = $doc.CreateElement('w','szCs',$wNs)
        [void]$szCs.Attributes.Append((New-WAttr $doc 'val' '28'))
        [void]$rPr.AppendChild($szCs)
        $lang = $doc.CreateElement('w','lang',$wNs)
        [void]$lang.Attributes.Append((New-WAttr $doc 'val' 'uk-UA'))
        [void]$rPr.AppendChild($lang)
        [void]$r.AppendChild($rPr)
    }

    function New-Paragraph([xml]$doc, [string]$text, [string]$kind) {
        $isHeading = $kind -eq 'H'
        $isSub = $kind -eq 'S'
        $isFigure = $kind -eq 'F'
        $isCaption = $kind -eq 'C'
        $p = $doc.CreateElement('w','p',$wNs)
        $pPr = $doc.CreateElement('w','pPr',$wNs)
        $styleVal = if ($isHeading) {'ac'} elseif ($isSub) {'ae'} elseif ($isCaption) {'af4'} else {'af0'}
        $pStyle = $doc.CreateElement('w','pStyle',$wNs)
        [void]$pStyle.Attributes.Append((New-WAttr $doc 'val' $styleVal))
        [void]$pPr.AppendChild($pStyle)
        $spacing = $doc.CreateElement('w','spacing',$wNs)
        [void]$spacing.Attributes.Append((New-WAttr $doc 'after' ($(if ($isFigure) {'120'} else {'0'}))))
        [void]$spacing.Attributes.Append((New-WAttr $doc 'line' '360'))
        [void]$spacing.Attributes.Append((New-WAttr $doc 'lineRule' 'auto'))
        [void]$pPr.AppendChild($spacing)
        if (-not ($isHeading -or $isSub -or $isFigure -or $isCaption)) {
            $ind = $doc.CreateElement('w','ind',$wNs)
            [void]$ind.Attributes.Append((New-WAttr $doc 'firstLine' '709'))
            [void]$pPr.AppendChild($ind)
        }
        $jc = $doc.CreateElement('w','jc',$wNs)
        $align = if ($isHeading -or $isSub -or $isFigure -or $isCaption) {'center'} else {'both'}
        [void]$jc.Attributes.Append((New-WAttr $doc 'val' $align))
        [void]$pPr.AppendChild($jc)
        [void]$p.AppendChild($pPr)
        $r = $doc.CreateElement('w','r',$wNs)
        Add-RunProps $doc $r ($isHeading -or $isSub) $isFigure ($(if ($isFigure) {'666666'} else {'000000'}))
        $t = $doc.CreateElement('w','t',$wNs)
        $t.InnerText = $text
        [void]$r.AppendChild($t)
        [void]$p.AppendChild($r)
        return $p
    }

    foreach ($item in $items) {
        $p = New-Paragraph $xml $item.Text $item.Kind
        if ($sectPr) { [void]$body.InsertBefore($p, $sectPr) } else { [void]$body.AppendChild($p) }
    }
    $entry.Delete()
    $newEntry = $zip.CreateEntry('word/document.xml')
    $writer = [IO.StreamWriter]::new($newEntry.Open(), [Text.UTF8Encoding]::new($false))
    $xml.Save($writer)
    $writer.Close()
}
finally {
    $zip.Dispose()
}

Write-Output "Updated: $path"
Write-Output "Backup: $backup"
Write-Output "Paragraphs: $($items.Count)"
