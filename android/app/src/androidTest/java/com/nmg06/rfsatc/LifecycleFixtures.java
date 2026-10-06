package com.nmg06.rfsatc;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import java.io.FileNotFoundException;
import java.io.OutputStream;

/** Test APK only: fixed harmless image/text fixtures, no files or user data exposed. */
public class LifecycleFixtures extends ContentProvider {
    static final String AUTHORITY="com.nmg06.rfsatc.test.lifecycle-fixtures";
    static final byte[] PNG=android.util.Base64.decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aPq0AAAAASUVORK5CYII=",android.util.Base64.DEFAULT);
    @Override public boolean onCreate(){return true;}
    @Override public String getType(Uri uri){return "image".equals(uri.getLastPathSegment())?"image/png":"text/plain";}
    @Override public Cursor query(Uri uri,String[] projection,String selection,String[] arguments,String order){
        MatrixCursor result=new MatrixCursor(new String[]{android.provider.OpenableColumns.DISPLAY_NAME,android.provider.OpenableColumns.SIZE});result.addRow(new Object[]{"image".equals(uri.getLastPathSegment())?"fixture.png":"invalid.txt",PNG.length});return result;
    }
    @Override public ParcelFileDescriptor openFile(Uri uri,String mode) throws FileNotFoundException {
        if(!"r".equals(mode))throw new FileNotFoundException("Read-only fixture");
        try{ParcelFileDescriptor[] pipe=ParcelFileDescriptor.createPipe();new Thread(()->{try(OutputStream out=new ParcelFileDescriptor.AutoCloseOutputStream(pipe[1])){out.write(PNG);}catch(Exception ignored){}}).start();return pipe[0];}
        catch(Exception e){throw new FileNotFoundException(e.toString());}
    }
    @Override public Uri insert(Uri uri,ContentValues values){throw new UnsupportedOperationException();}
    @Override public int delete(Uri uri,String selection,String[] arguments){throw new UnsupportedOperationException();}
    @Override public int update(Uri uri,ContentValues values,String selection,String[] arguments){throw new UnsupportedOperationException();}
}
